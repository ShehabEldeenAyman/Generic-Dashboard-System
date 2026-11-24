// Tests for the Agent orchestration logic in src/orchestration.js (run with: npm test).
import assert from 'node:assert/strict'
import { beforeEach, describe, test } from 'node:test'
import {
  STARTER_QUERY, dependencyIds, dependsOn, exampleEnvironment, inputStatus, loadState, newAgent, newEnvironment, newId,
  outputIri, producesGraph, queryForm, referencedRefs, renameReferences, resolveReferences, runOrder, saveState,
  signature, slugify, uniqueRef,
} from '../src/orchestration.js'

const BASE = 'https://example.org/graphs/orchestration/'

function agent(id, { ref = id, query = 'SELECT * WHERE { ?s ?p ?o }', sources = [], output = null, lastRun = null } = {}) {
  return { id, name: id, ref, query, sources, output, lastRun }
}

const environment = (agents) => ({ id: 'env123456', name: 'Test', agents })
const out = (id) => outputIri(BASE, 'env123456', id)

describe('ids, names, and references', () => {
  test('ids are 10 lowercase letters or digits and differ', () => {
    const ids = new Set(Array.from({ length: 200 }, newId))
    assert.equal(ids.size, 200)
    for (const id of ids) assert.match(id, /^[a-z0-9]{10}$/)
  })

  test('slugify makes readable reference keys', () => {
    assert.equal(slugify('High readings!'), 'high-readings')
    assert.equal(slugify('  Ünïcödé  names '), 'unicode-names')
    assert.equal(slugify('***'), 'agent')
    assert.equal(slugify('x'.repeat(60)).length, 40)
  })

  test('reference keys are unique within an environment', () => {
    const agents = [agent('a', { ref: 'alerts' }), agent('b', { ref: 'alerts-2' })]
    assert.equal(uniqueRef('Alerts', agents), 'alerts-3')
    assert.equal(uniqueRef('Alerts', agents, 'a'), 'alerts')
    assert.equal(uniqueRef('Sensors', agents), 'sensors')
  })

  test('output graphs are named after the environment and the agent', () => {
    assert.equal(outputIri(BASE, 'env1', 'agent1'), `${BASE}env1/agent1`)
  })
})

describe('reading queries', () => {
  test('the query form ignores comments, strings, and IRIs', () => {
    assert.equal(queryForm('SELECT * WHERE { ?s ?p ?o }'), 'SELECT')
    assert.equal(queryForm('# select everything\nconstruct { ?s ?p ?o } where { ?s ?p ?o }'), 'CONSTRUCT')
    assert.equal(queryForm('PREFIX ex: <http://example.org/select#>\nASK { ?s ex:p "SELECT" }'), 'ASK')
    assert.equal(queryForm('DESCRIBE <http://example.org/a>'), 'DESCRIBE')
    assert.equal(queryForm('PREFIX ex: <http://example.org/>'), null)
    assert.equal(queryForm(''), null)
  })

  test('only CONSTRUCT and DESCRIBE produce a graph', () => {
    assert.equal(producesGraph('CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }'), true)
    assert.equal(producesGraph('DESCRIBE <http://example.org/a>'), true)
    assert.equal(producesGraph('SELECT * WHERE { ?s ?p ?o }'), false)
  })

  test('references in comments do not count', () => {
    const query = '# GRAPH <agent:old>\nSELECT * { GRAPH <agent:alerts> { ?s ?p ?o } GRAPH <agent:alerts> {} }'
    assert.deepEqual(referencedRefs(query), ['alerts'])
  })

  test('references are replaced by output graphs, and unknown ones are reported', () => {
    const env = environment([agent('a1', { ref: 'alerts' })])
    const { query, missing } = resolveReferences('SELECT * { GRAPH <agent:alerts> {} GRAPH <agent:nope> {} }', env, BASE)
    assert.equal(query, `SELECT * { GRAPH <${out('a1')}> {} GRAPH <agent:nope> {} }`)
    assert.deepEqual(missing, ['nope'])
  })

  test('renaming replaces only the exact reference', () => {
    const query = 'GRAPH <agent:high> {} GRAPH <agent:high-2> {} GRAPH <agent:high> {}'
    assert.equal(renameReferences(query, 'high', 'peak'), 'GRAPH <agent:peak> {} GRAPH <agent:high-2> {} GRAPH <agent:peak> {}')
  })
})

describe('dependencies', () => {
  const chain = () => environment([
    agent('c', { sources: [out('b')] }),
    agent('a', { query: 'CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }' }),
    agent('b', { query: 'CONSTRUCT { ?s ?p ?o } WHERE { GRAPH <agent:a> { ?s ?p ?o } }' }),
  ])

  test('an agent depends on the outputs it ticks and the agents it references', () => {
    const env = chain()
    assert.deepEqual(dependencyIds(env.agents[0], env, BASE), ['b'])
    assert.deepEqual(dependencyIds(env.agents[2], env, BASE), ['a'])
    assert.deepEqual(dependencyIds(env.agents[1], env, BASE), [])
  })

  test('dependencies are followed through other agents', () => {
    const env = chain()
    assert.equal(dependsOn(env, BASE, 'c', 'a'), true)
    assert.equal(dependsOn(env, BASE, 'a', 'c'), false)
  })

  test('agents run after the agents they read from', () => {
    const { order, cyclic } = runOrder(chain(), BASE)
    assert.deepEqual(order.map((item) => item.id), ['a', 'b', 'c'])
    assert.deepEqual(cyclic, [])
  })

  test('agents that read from each other are reported instead of run', () => {
    const env = environment([
      agent('x', { sources: [out('y')] }),
      agent('y', { sources: [out('x')] }),
      agent('z'),
    ])
    const { order, cyclic } = runOrder(env, BASE)
    assert.deepEqual(order.map((item) => item.id), ['z'])
    assert.deepEqual(cyclic.map((item) => item.id), ['x', 'y'])
    assert.equal(dependsOn(env, BASE, 'x', 'x'), true)
  })
})

describe('run status', () => {
  test('the signature changes when the query or the sources change', () => {
    const base = agent('a', { sources: ['https://example.org/g'] })
    assert.equal(signature(base), signature({ ...base }))
    assert.notEqual(signature(base), signature({ ...base, query: `${base.query} ` }))
    assert.notEqual(signature(base), signature({ ...base, sources: [] }))
  })

  test('stale, missing, and edited inputs are detected', () => {
    const producer = agent('p', { query: 'CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }', output: { graph: out('p'), triples: 3, version: 'v2' } })
    const consumer = agent('c', { sources: [out('p')] })
    consumer.lastRun = { status: 'success', inputs: { p: 'v1' }, signature: signature(consumer) }
    let env = environment([producer, consumer])
    assert.deepEqual(inputStatus(consumer, env, BASE).stale.map((item) => item.id), ['p'])
    assert.equal(inputStatus(consumer, env, BASE).edited, false)

    consumer.lastRun = { ...consumer.lastRun, inputs: { p: 'v2' } }
    assert.deepEqual(inputStatus(consumer, env, BASE).stale, [])

    const edited = { ...consumer, query: 'SELECT ?s WHERE { ?s ?p ?o }' }
    env = environment([producer, edited])
    assert.equal(inputStatus(edited, env, BASE).edited, true)

    const waiting = environment([{ ...producer, output: null }, consumer])
    assert.deepEqual(inputStatus(consumer, waiting, BASE).missing.map((item) => item.id), ['p'])
  })

  test('agents that never ran successfully are not stale', () => {
    const producer = agent('p', { output: { graph: out('p'), triples: 1, version: 'v1' } })
    const failed = agent('c', { sources: [out('p')], lastRun: { status: 'error', inputs: {} } })
    assert.deepEqual(inputStatus(failed, environment([producer, failed]), BASE).stale, [])
  })
})

describe('creating environments and agents', () => {
  test('new agents and environments get unused names', () => {
    const env = newEnvironment([{ name: 'Environment 1' }, { name: 'Environment 3' }])
    assert.equal(env.name, 'Environment 4')
    assert.match(env.id, /^[a-z0-9]{10}$/)
    env.agents.push(newAgent(env, ['https://example.org/g']))
    const second = newAgent(env, [])
    assert.equal(env.agents[0].name, 'Agent 1')
    assert.equal(env.agents[0].query, STARTER_QUERY)
    assert.deepEqual(env.agents[0].sources, ['https://example.org/g'])
    assert.equal(second.name, 'Agent 2')
    assert.notEqual(second.ref, env.agents[0].ref)
  })

  test('the example chains three agents through the first one\'s output', () => {
    const graph = 'https://example.org/graphs/waterinfo-sample'
    const env = exampleEnvironment(BASE, graph)
    const [high, perSensor, below] = env.agents
    assert.equal(queryForm(high.query), 'CONSTRUCT')
    assert.deepEqual(high.sources, [graph])
    assert.deepEqual(perSensor.sources, [outputIri(BASE, env.id, high.id)])
    assert.deepEqual(below.sources, [])
    assert.deepEqual(referencedRefs(below.query), ['high-readings'])
    assert.ok(below.query.includes(`<${graph}>`))
    assert.equal(runOrder(env, BASE).order[0].id, high.id)
    assert.deepEqual(resolveReferences(below.query, env, BASE).missing, [])
  })
})

describe('browser storage', () => {
  let store
  beforeEach(() => {
    store = new Map()
    globalThis.localStorage = {
      getItem: (key) => (store.has(key) ? store.get(key) : null),
      setItem: (key, value) => store.set(key, String(value)),
    }
  })

  test('state survives a save and a load', () => {
    const state = { environments: [newEnvironment([])], activeId: null }
    saveState(state)
    assert.deepEqual(loadState(), state)
  })

  test('missing or unreadable storage gives an empty state', () => {
    assert.deepEqual(loadState(), { environments: [], activeId: null })
    store.set('semantic-data-studio.orchestration.v1', '{not json')
    assert.deepEqual(loadState(), { environments: [], activeId: null })
    globalThis.localStorage = { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('full') } }
    assert.deepEqual(loadState(), { environments: [], activeId: null })
    assert.doesNotThrow(() => saveState({ environments: [], activeId: null }))
  })
})
