// Environments and agents for Agent orchestration. They are kept in this browser
// (localStorage); the agents' output graphs live in Fuseki.

const STORAGE_KEY = 'semantic-data-studio.orchestration.v1'

export const STARTER_QUERY = `SELECT ?subject ?predicate ?object
WHERE {
  ?subject ?predicate ?object .
}
LIMIT 25`

export function newId() {
  const bytes = new Uint8Array(10)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (byte) => (byte % 36).toString(36)).join('')
}

export function loadState() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    if (value && Array.isArray(value.environments)) return value
  } catch { /* storage unavailable or unreadable */ }
  return { environments: [], activeId: null }
}

export function saveState(state) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)) } catch { /* storage unavailable or full */ }
}

export function slugify(name) {
  return name.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) || 'agent'
}

/** A reference key for an agent, unique within its environment: <agent:key>. */
export function uniqueRef(name, agents, exceptId) {
  const taken = new Set(agents.filter((agent) => agent.id !== exceptId).map((agent) => agent.ref))
  const base = slugify(name)
  let ref = base
  for (let suffix = 2; taken.has(ref); suffix += 1) ref = `${base}-${suffix}`
  return ref
}

export const outputIri = (base, environmentId, agentId) => `${base}${environmentId}/${agentId}`

/** Remove comments, and optionally IRIs and strings, so that only query syntax is left. */
function plainQuery(query, { keepIris = false } = {}) {
  let out = ''
  let index = 0
  while (index < query.length) {
    const char = query[index]
    if (char === '#') {
      const newline = query.indexOf('\n', index)
      index = newline === -1 ? query.length : newline
      continue
    }
    if (char === '<') {
      const close = query.indexOf('>', index + 1)
      if (close !== -1 && !/\s/.test(query.slice(index + 1, close))) {
        out += keepIris ? query.slice(index, close + 1) : ' '
        index = close + 1
        continue
      }
    }
    if (char === '"' || char === "'") {
      const quote = query.startsWith(char.repeat(3), index) ? char.repeat(3) : char
      let end = index + quote.length
      while (end < query.length && !query.startsWith(quote, end)) {
        if (quote.length === 1 && query[end] === '\n') break
        end += query[end] === '\\' ? 2 : 1
      }
      out += ' '
      index = end + quote.length
      continue
    }
    out += char
    index += 1
  }
  return out
}

/** SELECT, CONSTRUCT, ASK, or DESCRIBE, or null when it cannot be told. */
export function queryForm(query) {
  const match = plainQuery(query).match(/\b(SELECT|CONSTRUCT|ASK|DESCRIBE)\b/i)
  return match ? match[1].toUpperCase() : null
}

export const producesGraph = (query) => ['CONSTRUCT', 'DESCRIBE'].includes(queryForm(query))

const REFERENCE = /<agent:([a-z0-9-]+)>/g

/** The agent references a query uses, ignoring comments. */
export function referencedRefs(query) {
  return [...new Set([...plainQuery(query, { keepIris: true }).matchAll(REFERENCE)].map((match) => match[1]))]
}

/** Replace <agent:key> references with the agents' output graphs. */
export function resolveReferences(query, environment, base) {
  const known = new Map(environment.agents.map((agent) => [agent.ref, agent]))
  const missing = referencedRefs(query).filter((ref) => !known.has(ref))
  const text = query.replace(REFERENCE, (match, ref) => (
    known.has(ref) ? `<${outputIri(base, environment.id, known.get(ref).id)}>` : match
  ))
  return { query: text, missing }
}

export const renameReferences = (query, oldRef, newRef) => query.split(`<agent:${oldRef}>`).join(`<agent:${newRef}>`)

/** The agents whose output this agent reads, through its sources or its references. */
export function dependencyIds(agent, environment, base) {
  const refs = referencedRefs(agent.query)
  return environment.agents
    .filter((other) => other.id !== agent.id && (
      agent.sources.includes(outputIri(base, environment.id, other.id)) || refs.includes(other.ref)
    ))
    .map((other) => other.id)
}

/** True when agentId reads targetId's output, directly or through other agents. */
export function dependsOn(environment, base, agentId, targetId, seen = new Set()) {
  if (seen.has(agentId)) return false
  seen.add(agentId)
  const agent = environment.agents.find((item) => item.id === agentId)
  if (!agent) return false
  return dependencyIds(agent, environment, base)
    .some((id) => id === targetId || dependsOn(environment, base, id, targetId, seen))
}

/** Agents in an order where every agent runs after the agents it reads from. */
export function runOrder(environment, base) {
  const dependencies = new Map(environment.agents.map((agent) => [agent.id, dependencyIds(agent, environment, base)]))
  const order = []
  const done = new Set()
  let progress = true
  while (progress && order.length < environment.agents.length) {
    progress = false
    for (const agent of environment.agents) {
      if (!done.has(agent.id) && dependencies.get(agent.id).every((id) => done.has(id))) {
        order.push(agent)
        done.add(agent.id)
        progress = true
      }
    }
  }
  return { order, cyclic: environment.agents.filter((agent) => !done.has(agent.id)) }
}

/** A short fingerprint of what an agent runs, to notice edits made after a run. */
export function signature(agent) {
  const text = JSON.stringify([agent.query, agent.sources])
  let hash = 2166136261
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(36)
}

/** Which inputs changed since the agent last ran, and which have no output yet. */
export function inputStatus(agent, environment, base) {
  const dependencies = dependencyIds(agent, environment, base)
    .map((id) => environment.agents.find((item) => item.id === id))
  const missing = dependencies.filter((dependency) => !dependency.output)
  const recorded = agent.lastRun?.status === 'success' ? agent.lastRun.inputs || {} : null
  const stale = recorded
    ? dependencies.filter((dependency) => dependency.output && recorded[dependency.id] !== dependency.output.version)
    : []
  const edited = Boolean(agent.lastRun) && agent.lastRun.signature !== signature(agent)
  return { stale, missing, edited }
}

export function newAgent(environment, sources) {
  const name = `Agent ${environment.agents.length + 1}`
  return { id: newId(), name, ref: uniqueRef(name, environment.agents), query: STARTER_QUERY, sources, lastRun: null, output: null }
}

export function newEnvironment(environments) {
  const names = new Set(environments.map((environment) => environment.name))
  let index = environments.length + 1
  while (names.has(`Environment ${index}`)) index += 1
  return { id: newId(), name: `Environment ${index}`, createdAt: new Date().toISOString(), agents: [] }
}

/** Three agents for the sample water data: a CONSTRUCT and two agents that build on it. */
export function exampleEnvironment(base, graph) {
  const environment = { id: newId(), name: 'High conductivity example', createdAt: new Date().toISOString(), agents: [] }
  const high = {
    id: newId(), name: 'High readings', ref: 'high-readings', sources: [graph], lastRun: null, output: null,
    query: `PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX ex:   <https://example.org/orchestration#>

# Readings of 15,000 µS/cm or more. The result is saved as this agent's output graph.
CONSTRUCT {
  ?reading a ex:HighReading ;
           ex:sensor ?sensor ;
           ex:value ?value ;
           ex:time ?time .
}
WHERE {
  ?reading sosa:madeBySensor ?sensor ;
           sosa:hasSimpleResult ?value ;
           sosa:resultTime ?time .
  FILTER(?value >= 15000)
}`,
  }
  const perSensor = {
    id: newId(), name: 'High readings per sensor', ref: 'high-readings-per-sensor', lastRun: null, output: null,
    sources: [outputIri(base, environment.id, high.id)],
    query: `PREFIX ex: <https://example.org/orchestration#>

# Reads the output of "High readings", which is ticked under Reads from.
SELECT ?sensor (COUNT(?reading) AS ?highReadings) (MAX(?value) AS ?peak)
WHERE {
  ?reading a ex:HighReading ;
           ex:sensor ?sensor ;
           ex:value ?value .
}
GROUP BY ?sensor
ORDER BY DESC(?highReadings)`,
  }
  const below = {
    id: newId(), name: 'Readings below the threshold', ref: 'readings-below-the-threshold', sources: [], lastRun: null, output: null,
    query: `PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX ex:   <https://example.org/orchestration#>

# Nothing is ticked under Reads from, so the query names its graphs itself.
# <agent:high-readings> stands for the output graph of "High readings".
SELECT (COUNT(?reading) AS ?readingsBelowThreshold)
WHERE {
  GRAPH <${graph}> { ?reading a sosa:Observation }
  FILTER NOT EXISTS { GRAPH <agent:high-readings> { ?reading a ex:HighReading } }
}`,
  }
  environment.agents = [high, perSensor, below]
  return environment
}
