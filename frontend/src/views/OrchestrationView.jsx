import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { formatNumber, isAgentOutput, shortIri, timeAgo } from '../format.js'
import QueryResults from '../components/QueryResults.jsx'
import { Badge, Button, Card, CopyButton, EmptyState, Icon, Notice, Spinner } from '../components/ui.jsx'
import {
  dependencyIds, dependsOn, exampleEnvironment, inputStatus, loadState, newAgent, newEnvironment, outputIri,
  producesGraph, queryForm, renameReferences, resolveReferences, runOrder, saveState, signature, slugify, uniqueRef,
} from '../orchestration.js'

const plural = (count, noun) => `${formatNumber(count)} ${noun}${count === 1 ? '' : 's'}`

function summaryOf(result) {
  if (result.type === 'graph') return `${plural(result.triples, 'triple')} saved`
  if (result.type === 'ask') return result.boolean ? 'Yes' : 'No'
  return plural(result.row_count, 'row')
}

function AgentStatus({ agent, running, status, unresolved }) {
  if (running) return <Badge tone="info"><Spinner size={10} /> Running</Badge>
  if (agent.lastRun?.status === 'error') return <Badge tone="danger" dot>Failed</Badge>
  if (unresolved.length) return <Badge tone="danger" dot>Unknown reference</Badge>
  if (status.missing.length) return <Badge tone="warning" dot>Waiting for input</Badge>
  if (status.stale.length) return <Badge tone="warning" dot>Stale</Badge>
  if (status.edited) return <Badge tone="warning" dot>Edited</Badge>
  if (agent.lastRun?.status === 'success') return <Badge tone="success" dot>{agent.lastRun.summary}</Badge>
  return <Badge dot>Not run</Badge>
}

function SourcePicker({ agent, published, outputOptions, unknownSources, onToggle }) {
  const checked = (iri) => agent.sources.includes(iri)
  return (
    <fieldset className="source-picker">
      <legend>Reads from</legend>
      <div className="source-group">
        <span>Graphs in Fuseki</span>
        {published.length ? published.map((graph) => (
          <label key={graph.uri} className="source-option" title={graph.uri}>
            <input type="checkbox" checked={checked(graph.uri)} onChange={() => onToggle(graph.uri)} />
            <span>{shortIri(graph.uri)}</span>
            <small>{formatNumber(graph.triples)} triples</small>
          </label>
        )) : <p className="muted small">No published graphs. Publish one from Knowledge graph.</p>}
      </div>
      {outputOptions.length > 0 && (
        <div className="source-group">
          <span>Agent outputs</span>
          {outputOptions.map((option) => (
            <label key={option.iri} className={`source-option ${option.blocked ? 'disabled' : ''}`}
              title={option.blocked ? `“${option.agent.name}” reads from this agent, so this agent cannot read from it.` : option.iri}>
              <input type="checkbox" checked={checked(option.iri)} disabled={option.blocked && !checked(option.iri)} onChange={() => onToggle(option.iri)} />
              <span>Output of “{option.agent.name}”</span>
              <small>{option.agent.output ? plural(option.triples ?? option.agent.output.triples, 'triple') : 'not run yet'}</small>
            </label>
          ))}
        </div>
      )}
      {unknownSources.map((iri) => (
        <label key={iri} className="source-option" title={iri}>
          <input type="checkbox" checked onChange={() => onToggle(iri)} />
          <span>{shortIri(iri)}</span>
          <small className="warn-text">not in Fuseki</small>
        </label>
      ))}
      <p className="field-hint">{agent.sources.length
        ? 'The ticked graphs are combined, so the query needs no FROM or GRAPH to read them.'
        : 'Nothing ticked: the query only sees the graphs it names itself, with GRAPH <…>.'}</p>
    </fieldset>
  )
}

function AgentResult({ result, agent, onUseOutput }) {
  if (result.type !== 'graph') {
    return <QueryResults result={result} filename={slugify(agent.name)} />
  }
  const previewTable = {
    type: 'select', variables: result.preview.variables, rows: result.preview.rows,
    row_count: result.preview.rows.length, truncated: false,
  }
  return (
    <div className="agent-result">
      <Notice tone="success" title={`Saved ${plural(result.triples, 'triple')} to this agent's output graph`}>
        Other agents can read it: tick “Output of ‘{agent.name}’” under Reads from, or insert a reference to it.
      </Notice>
      <div className="source-name">
        <code>{result.output_graph}</code>
        <CopyButton text={result.output_graph} />
        <Button variant="secondary" icon="plus" onClick={onUseOutput}>New agent reading this output</Button>
      </div>
      {result.preview.rows.length > 0 && (
        <>
          <p className="muted small">The first {result.preview.rows.length} triples of the output:</p>
          <QueryResults result={previewTable} filename={`${slugify(agent.name)}-preview`} />
        </>
      )}
    </div>
  )
}

function AgentCard({
  environment, agent, index, base, published, storedOutputs, storeLoaded, fusekiOnline, result,
  running, busy, onChange, onRename, onRun, onDelete, onUseOutput,
}) {
  const editor = useRef(null)
  const form = queryForm(agent.query)
  const status = inputStatus(agent, environment, base)
  const unresolved = resolveReferences(agent.query, environment, base).missing
  const outputOptions = environment.agents
    .filter((other) => other.id !== agent.id)
    .map((other) => {
      const iri = outputIri(base, environment.id, other.id)
      return { agent: other, iri, triples: storedOutputs.get(iri), blocked: dependsOn(environment, base, other.id, agent.id) }
    })
    .filter((option) => producesGraph(option.agent.query) || option.agent.output || agent.sources.includes(option.iri))
  const unknownSources = storeLoaded
    ? agent.sources.filter((iri) => !published.some((graph) => graph.uri === iri) && !outputOptions.some((option) => option.iri === iri))
    : []
  const referenceOptions = outputOptions.filter((option) => !option.blocked)
  const outputMissing = Boolean(agent.output?.triples) && storeLoaded && fusekiOnline && !storedOutputs.has(agent.output.graph)

  function toggleSource(iri) {
    onChange({ sources: agent.sources.includes(iri) ? agent.sources.filter((item) => item !== iri) : [...agent.sources, iri] })
  }

  function insert(text) {
    if (!text) return
    const element = editor.current
    const start = element?.selectionStart ?? agent.query.length
    const end = element?.selectionEnd ?? start
    onChange({ query: agent.query.slice(0, start) + text + agent.query.slice(end) })
    requestAnimationFrame(() => {
      if (!element) return
      element.focus()
      element.setSelectionRange(start + text.length, start + text.length)
    })
  }

  const names = (agents) => agents.map((item) => `“${item.name}”`).join(', ')

  return (
    <section className="card agent-card" id={`agent-${agent.id}`} aria-label={`Agent ${agent.name}`}>
      <div className="card-body">
        <div className="agent-head">
          <span className="agent-number">{index + 1}</span>
          <input className="inline-input" key={agent.name} defaultValue={agent.name} aria-label="Agent name"
            onBlur={(event) => onRename(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter') event.currentTarget.blur() }} />
          <Badge tone={producesGraph(agent.query) ? 'info' : 'neutral'}>{form || 'SPARQL'}</Badge>
          <AgentStatus agent={agent} running={running} status={status} unresolved={unresolved} />
          <div className="button-row">
            <Button icon="play" busy={running} disabled={busy || !fusekiOnline || !agent.query.trim()} onClick={onRun}>Run</Button>
            <Button variant="ghost" icon="trash" disabled={busy} onClick={onDelete} aria-label={`Delete the agent ${agent.name}`} title="Delete agent" />
          </div>
        </div>

        {agent.lastRun?.status === 'error' && <Notice tone="danger" title="The last run failed">{agent.lastRun.error}</Notice>}
        {unresolved.length > 0 && (
          <Notice tone="danger" title="Unknown reference">
            {unresolved.map((ref) => `<agent:${ref}>`).join(', ')} does not match an agent here. Use Insert reference to pick one.
          </Notice>
        )}
        {status.missing.length > 0 && (
          <Notice tone="warning" title="Waiting for input">{names(status.missing)} has not produced an output yet. Run it first, or use Run all.</Notice>
        )}
        {status.stale.length > 0 && (
          <Notice tone="warning" title="Stale">{names(status.stale)} ran again after this agent. Run this agent again to use the new output.</Notice>
        )}
        {outputMissing && (
          <Notice tone="warning" title="Output graph not found">This agent's output is no longer in Fuseki, for example after a restart. Run the agent again.</Notice>
        )}

        <SourcePicker agent={agent} published={published} outputOptions={outputOptions} unknownSources={unknownSources} onToggle={toggleSource} />

        <div className="editor-toolbar">
          <span className="field-label">Query{producesGraph(agent.query) && <span className="muted"> · the result is saved as this agent's output graph</span>}</span>
          <select className="insert-select" value="" aria-label="Insert a graph reference" onChange={(event) => insert(event.target.value)}>
            <option value="">Insert reference…</option>
            {referenceOptions.length > 0 && (
              <optgroup label="Agent outputs">
                {referenceOptions.map((option) => <option key={option.iri} value={`<agent:${option.agent.ref}>`}>Output of “{option.agent.name}”</option>)}
              </optgroup>
            )}
            {published.length > 0 && (
              <optgroup label="Graphs in Fuseki">
                {published.map((graph) => <option key={graph.uri} value={`<${graph.uri}>`}>{shortIri(graph.uri)}</option>)}
              </optgroup>
            )}
          </select>
        </div>
        <div className="code-editor">
          <textarea ref={editor} spellCheck="false" value={agent.query} aria-label={`SPARQL query of ${agent.name}`}
            onChange={(event) => onChange({ query: event.target.value })}
            onKeyDown={(event) => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !busy) onRun() }} />
          <span className="code-editor-meta">Ctrl+Enter to run</span>
        </div>

        {result ? (
          <>
            <AgentResult result={result} agent={agent} onUseOutput={onUseOutput} />
            <p className="muted small">Ran in {result.duration_seconds} s.</p>
          </>
        ) : agent.lastRun?.status === 'success' && (
          <p className="muted small">Last run {timeAgo(agent.lastRun.at)}: {agent.lastRun.summary}. Run it again to see the results.</p>
        )}
      </div>
    </section>
  )
}

export default function OrchestrationView({ config, store, onRefreshStore, active }) {
  const [state, setState] = useState(loadState)
  const [results, setResults] = useState({})
  const [running, setRunning] = useState(null)
  const [notice, setNotice] = useState(null)
  const stateRef = useRef(state)
  const base = config?.orchestration_graph_base || ''
  const fusekiOnline = Boolean(config?.fuseki?.connected)

  useEffect(() => {
    stateRef.current = state
    saveState(state)
  }, [state])

  useEffect(() => { if (active && fusekiOnline) onRefreshStore() }, [active, fusekiOnline, onRefreshStore])

  const environment = state.environments.find((item) => item.id === state.activeId) || state.environments[0] || null
  const graphs = store.data?.graphs || []
  const published = graphs.filter((graph) => !isAgentOutput(graph.uri, config))
  const storedOutputs = new Map(graphs.filter((graph) => isAgentOutput(graph.uri, config)).map((graph) => [graph.uri, graph.triples]))

  const updateEnvironment = useCallback((environmentId, change) => {
    setState((current) => ({
      ...current,
      environments: current.environments.map((item) => (item.id === environmentId ? change(item) : item)),
    }))
  }, [])

  const updateAgent = useCallback((environmentId, agentId, patch) => {
    updateEnvironment(environmentId, (item) => ({
      ...item,
      agents: item.agents.map((agent) => (agent.id === agentId ? { ...agent, ...patch } : agent)),
    }))
  }, [updateEnvironment])

  function addEnvironment(created) {
    setState((current) => ({ ...current, environments: [...current.environments, created], activeId: created.id }))
  }

  function createExample() {
    const graph = published.find((item) => /waterinfo/i.test(item.uri)) || published[0]
    if (graph && base) addEnvironment(exampleEnvironment(base, graph.uri))
  }

  async function deleteEnvironment(target) {
    const count = plural(target.agents.length, 'agent')
    if (!window.confirm(`Delete “${target.name}” and its ${count}? Their output graphs are removed from Fuseki.`)) return
    try {
      await api.dropAgentOutputs(target.id)
    } catch (reason) {
      setNotice({ tone: 'warning', title: 'The output graphs could not be removed from Fuseki', text: reason.message })
    }
    setState((current) => {
      const environments = current.environments.filter((item) => item.id !== target.id)
      return { ...current, environments, activeId: environments[0]?.id || null }
    })
    onRefreshStore()
  }

  function renameEnvironment(target, name) {
    const trimmed = name.trim()
    if (trimmed && trimmed !== target.name) updateEnvironment(target.id, (item) => ({ ...item, name: trimmed }))
  }

  function addAgent(target, sources) {
    const lastOutput = [...target.agents].reverse().find((agent) => agent.output)
    const defaults = sources
      ?? (lastOutput ? [outputIri(base, target.id, lastOutput.id)] : published[0] ? [published[0].uri] : [])
    const agent = newAgent(target, defaults)
    updateEnvironment(target.id, (item) => ({ ...item, agents: [...item.agents, agent] }))
    requestAnimationFrame(() => document.getElementById(`agent-${agent.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  function renameAgent(target, agent, name) {
    const trimmed = name.trim()
    if (!trimmed || trimmed === agent.name) return
    const ref = uniqueRef(trimmed, target.agents, agent.id)
    const rewrite = (other) => {
      const query = renameReferences(other.query, agent.ref, ref)
      if (query === other.query) return other
      const next = { ...other, query }
      // Only the reference changed, so a run that was up to date stays up to date.
      if (other.lastRun?.signature === signature(other)) next.lastRun = { ...other.lastRun, signature: signature(next) }
      return next
    }
    updateEnvironment(target.id, (item) => ({
      ...item,
      agents: item.agents.map((other) => (other.id === agent.id ? { ...rewrite(other), name: trimmed, ref } : rewrite(other))),
    }))
  }

  async function deleteAgent(target, agent) {
    const extra = agent.output ? ' Its output graph is removed from Fuseki.' : ''
    if (!window.confirm(`Delete the agent “${agent.name}”?${extra}`)) return
    if (agent.output) {
      try {
        await api.dropAgentOutputs(target.id, agent.id)
      } catch (reason) {
        setNotice({ tone: 'warning', title: 'The output graph could not be removed from Fuseki', text: reason.message })
      }
    }
    const iri = outputIri(base, target.id, agent.id)
    updateEnvironment(target.id, (item) => ({
      ...item,
      agents: item.agents
        .filter((other) => other.id !== agent.id)
        .map((other) => (other.sources.includes(iri) ? { ...other, sources: other.sources.filter((source) => source !== iri) } : other)),
    }))
    onRefreshStore()
  }

  /** Run one agent against the given state of its environment; returns what changed. */
  async function execute(target, agent) {
    const at = new Date().toISOString()
    const inputs = Object.fromEntries(dependencyIds(agent, target, base)
      .map((id) => [id, target.agents.find((item) => item.id === id)?.output?.version || null]))
    const run = { at, signature: signature(agent), inputs }
    const { query, missing } = resolveReferences(agent.query, target, base)
    if (missing.length) {
      const error = `Unknown reference ${missing.map((ref) => `<agent:${ref}>`).join(', ')}. Use Insert reference to pick an agent.`
      return { lastRun: { ...run, status: 'error', error }, output: agent.output, result: null }
    }
    try {
      const result = await api.runAgent({ environment_id: target.id, agent_id: agent.id, query, sources: agent.sources })
      const output = result.type === 'graph' ? { graph: result.output_graph, triples: result.triples, version: at } : null
      if (!output && agent.output) api.dropAgentOutputs(target.id, agent.id).catch(() => {})
      return { lastRun: { ...run, status: 'success', kind: result.type, summary: summaryOf(result) }, output, result }
    } catch (reason) {
      return { lastRun: { ...run, status: 'error', error: reason.message }, output: agent.output, result: null }
    }
  }

  function apply(environmentId, agentId, outcome) {
    updateAgent(environmentId, agentId, { lastRun: outcome.lastRun, output: outcome.output })
    setResults((current) => ({ ...current, [agentId]: outcome.result }))
  }

  async function runOne(target, agent) {
    setNotice(null)
    setRunning({ agentId: agent.id })
    const outcome = await execute(target, agent)
    apply(target.id, agent.id, outcome)
    setRunning(null)
    if (outcome.output || agent.output) onRefreshStore()
  }

  async function runAll(target) {
    setNotice(null)
    let current = stateRef.current.environments.find((item) => item.id === target.id) || target
    const { order, cyclic } = runOrder(current, base)
    if (cyclic.length) {
      setNotice({ tone: 'danger', title: 'Some agents read from each other', text: `Untick one of the outputs: ${cyclic.map((agent) => agent.name).join(', ')}.` })
      return
    }
    for (const [position, item] of order.entries()) {
      setRunning({ all: true, agentId: item.id, position: position + 1, total: order.length })
      const agent = current.agents.find((candidate) => candidate.id === item.id)
      const outcome = await execute(current, agent)
      apply(current.id, agent.id, outcome)
      current = {
        ...current,
        agents: current.agents.map((candidate) => (candidate.id === agent.id ? { ...candidate, lastRun: outcome.lastRun, output: outcome.output } : candidate)),
      }
      if (outcome.lastRun.status === 'error') {
        setNotice({ tone: 'danger', title: `Run all stopped at “${agent.name}”`, text: outcome.lastRun.error })
        break
      }
    }
    setRunning(null)
    onRefreshStore()
  }

  const examplePossible = Boolean(base) && published.length > 0

  return (
    <div className="view">
      <div className="view-header">
        <div><p className="eyebrow">Agent orchestration</p><h1>Chain SPARQL agents</h1>
          <p className="lede">Each agent is a SPARQL query. A CONSTRUCT agent saves its result as a temporary graph, which other agents can read instead of, or together with, your original graphs.</p></div>
      </div>

      {!fusekiOnline && (
        <Notice tone="warning" title="Fuseki is offline">Agents run against Fuseki. Start it, then refresh the status in the sidebar.</Notice>
      )}
      {notice && <Notice tone={notice.tone} title={notice.title} onClose={() => setNotice(null)}>{notice.text}</Notice>}

      <div className="query-layout">
        <Card title="Environments" icon="flow" subtitle={`${plural(state.environments.length, 'environment')} in this browser`}
          actions={<Button icon="plus" onClick={() => addEnvironment(newEnvironment(state.environments))} aria-label="New environment">New</Button>}>
          {state.environments.length ? (
            <div className="graph-list">
              {state.environments.map((item) => (
                <button key={item.id} className={`graph-item ${item.id === environment?.id ? 'active' : ''}`}
                  onClick={() => setState((current) => ({ ...current, activeId: item.id }))}>
                  <Icon name="flow" size={16} />
                  <span><strong>{item.name}</strong><small>{plural(item.agents.length, 'agent')}</small></span>
                </button>
              ))}
            </div>
          ) : <p className="muted small">Press New to create your first environment.</p>}
        </Card>

        {environment ? (
          <div className="stack">
            <Card>
              <div className="environment-head">
                <input className="inline-input title" key={`${environment.id}:${environment.name}`} defaultValue={environment.name}
                  aria-label="Environment name" onBlur={(event) => renameEnvironment(environment, event.target.value)}
                  onKeyDown={(event) => { if (event.key === 'Enter') event.currentTarget.blur() }} />
                <div className="button-row">
                  <Button icon="play" busy={Boolean(running?.all)} disabled={!environment.agents.length || Boolean(running) || !fusekiOnline}
                    onClick={() => runAll(environment)}>Run all</Button>
                  <Button variant="secondary" icon="plus" disabled={!base} onClick={() => addAgent(environment)}>Add agent</Button>
                  <Button variant="danger-ghost" icon="trash" disabled={Boolean(running)} onClick={() => deleteEnvironment(environment)}>Delete</Button>
                </div>
              </div>
              <p className="muted small">
                {plural(environment.agents.length, 'agent')} · saved in this browser · output graphs under <code>{base}{environment.id}/</code>
              </p>
              {running?.all && <div className="loading-row"><Spinner /> Running agent {running.position} of {running.total}</div>}
            </Card>

            <div className="agent-list">
              {environment.agents.map((agent, index) => (
                <AgentCard key={agent.id} environment={environment} agent={agent} index={index} base={base}
                  published={published} storedOutputs={storedOutputs} storeLoaded={Boolean(store.data)} fusekiOnline={fusekiOnline}
                  result={results[agent.id]} running={running?.agentId === agent.id} busy={Boolean(running)}
                  onChange={(patch) => updateAgent(environment.id, agent.id, patch)}
                  onRename={(name) => renameAgent(environment, agent, name)}
                  onRun={() => runOne(environment, agent)}
                  onDelete={() => deleteAgent(environment, agent)}
                  onUseOutput={() => addAgent(environment, [outputIri(base, environment.id, agent.id)])} />
              ))}
            </div>
            <button type="button" className="add-agent" disabled={!base} onClick={() => addAgent(environment)}>
              <Icon name="plus" size={18} /> Add agent
            </button>
          </div>
        ) : (
          <Card>
            <EmptyState icon="flow" title="Create an agent environment"
              action={(
                <div className="button-row">
                  <Button icon="plus" onClick={() => addEnvironment(newEnvironment(state.environments))}>New environment</Button>
                  <Button variant="secondary" icon="sparkle" disabled={!examplePossible} onClick={createExample}>Try an example</Button>
                </div>
              )}>
              An environment holds agents: SPARQL queries that can read your graphs and the graphs earlier agents constructed.
              {!examplePossible && ' The example needs a published graph, such as the sample water data.'}
            </EmptyState>
          </Card>
        )}
      </div>

      {environment && examplePossible && !environment.agents.length && (
        <p className="muted small">New to this? <button type="button" className="link-button" onClick={createExample}>Load the example environment</button> to see three agents working together.</p>
      )}
    </div>
  )
}
