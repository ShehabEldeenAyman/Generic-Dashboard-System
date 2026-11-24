import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { formatNumber, isAgentOutput, shortIri } from '../format.js'
import QueryResults from '../components/QueryResults.jsx'
import { Badge, Button, Card, EmptyState, Icon, Notice, Segmented, Spinner } from '../components/ui.jsx'

const OPERATION_ICONS = {
  graph_overview: 'layers', entity_types: 'table', property_usage: 'mapping',
  find_entities: 'search', describe_entity: 'file', search_text: 'search', sample_triples: 'code',
}

const starterQuery = (graph) => `SELECT ?subject ?predicate ?object
WHERE {
  GRAPH <${graph || 'https://example.org/graphs/your-graph'}> {
    ?subject ?predicate ?object .
  }
}
LIMIT 100`

function GraphButton({ graph, selected, onSelect, label }) {
  return (
    <button className={`graph-item ${selected === graph.uri ? 'active' : ''}`} onClick={() => onSelect(graph.uri)} title={graph.uri}>
      <Icon name={label ? 'flow' : 'layers'} size={16} />
      <span><strong>{label || shortIri(graph.uri)}</strong><small>{graph.uri}</small></span>
      <Badge>{formatNumber(graph.triples)}</Badge>
    </button>
  )
}

function GraphList({ store, config, selected, onSelect, onRefresh }) {
  const graphs = store.data?.graphs || []
  const published = graphs.filter((graph) => !isAgentOutput(graph.uri, config))
  const outputs = graphs.filter((graph) => isAgentOutput(graph.uri, config))
  return (
    <Card title="Graphs" icon="database" subtitle={store.data ? `${published.length} named graph${published.length === 1 ? '' : 's'}` : 'Triple store'}
      actions={<Button variant="ghost" icon="refresh" busy={store.loading} onClick={onRefresh} aria-label="Refresh graphs" />}>
      {store.error && <Notice tone="danger" title="Could not list graphs">{store.error}</Notice>}
      {!store.error && store.data && !graphs.length && (
        <EmptyState icon="database" title="No named graphs yet">Publish a dataset from the Knowledge graph workspace.</EmptyState>
      )}
      <div className="graph-list">
        {published.map((graph) => <GraphButton key={graph.uri} graph={graph} selected={selected} onSelect={onSelect} />)}
      </div>
      {outputs.length > 0 && (
        <div className="graph-list">
          <p className="eyebrow graph-group-label">Agent outputs (temporary)</p>
          {outputs.map((graph) => (
            <GraphButton key={graph.uri} graph={graph} selected={selected} onSelect={onSelect} label={`Output ${graph.uri.split('/').slice(-2).join('/')}`} />
          ))}
        </div>
      )}
      {store.data?.default_graph_triples > 0 && (
        <p className="muted small">The default graph also holds {formatNumber(store.data.default_graph_triples)} triples.</p>
      )}
    </Card>
  )
}

function OperationForm({ operation, graph, onRun, busy }) {
  const [values, setValues] = useState({})
  const fields = operation.parameters.filter((parameter) => parameter.kind !== 'graph')
  const needsGraph = operation.parameters.some((parameter) => parameter.kind === 'graph')
  const missing = fields.some((parameter) => parameter.required && !String(values[parameter.name] ?? '').trim())

  function submit(event) {
    event.preventDefault()
    const parameters = { ...values }
    if (needsGraph) parameters.graph = graph
    onRun(operation.id, parameters)
  }

  return (
    <form className="operation-form" onSubmit={submit}>
      <div className="operation-form-head">
        <span className="action-icon"><Icon name={OPERATION_ICONS[operation.id] || 'bolt'} size={20} /></span>
        <div><strong>{operation.title}</strong><p>{operation.description}</p></div>
      </div>
      {needsGraph && (
        <div className="field"><span className="field-label">Graph</span>
          {graph ? <code className="pill-code" title={graph}>{graph}</code> : <p className="field-error">Select a graph from the list.</p>}
        </div>
      )}
      {fields.map((parameter) => (
        <div className="field" key={parameter.name}>
          <label htmlFor={`op-${parameter.name}`}>{parameter.label}{!parameter.required && <span className="muted"> · optional</span>}</label>
          <input id={`op-${parameter.name}`} type={parameter.kind === 'integer' ? 'number' : 'text'}
            min={parameter.minimum} max={parameter.maximum}
            placeholder={parameter.default !== undefined ? String(parameter.default) : parameter.kind === 'iri' ? 'https://…' : ''}
            value={values[parameter.name] ?? ''} onChange={(event) => setValues({ ...values, [parameter.name]: event.target.value })} />
          <p className="field-hint">{parameter.description}</p>
        </div>
      ))}
      <div className="button-row">
        <Button type="submit" icon="play" busy={busy} disabled={(needsGraph && !graph) || missing}>Run operation</Button>
      </div>
    </form>
  )
}

export default function QueryView({ config, store, onRefreshStore, selectedGraph, onSelectGraph, active }) {
  const [tab, setTab] = useState('operations')
  const [catalog, setCatalog] = useState([])
  const [catalogError, setCatalogError] = useState('')
  const [operationId, setOperationId] = useState('graph_overview')
  const [query, setQuery] = useState(() => starterQuery(selectedGraph))
  const [queryEdited, setQueryEdited] = useState(false)
  const [outcome, setOutcome] = useState(null)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const fusekiOnline = Boolean(config?.fuseki?.connected)

  useEffect(() => {
    api.operations().then((value) => setCatalog(value.operations)).catch((reason) => setCatalogError(reason.message))
  }, [])

  useEffect(() => { if (active && fusekiOnline) onRefreshStore() }, [active, fusekiOnline, onRefreshStore])

  useEffect(() => {
    const graphs = store.data?.graphs || []
    if (graphs.length && !graphs.some((graph) => graph.uri === selectedGraph)) {
      onSelectGraph((graphs.find((graph) => !isAgentOutput(graph.uri, config)) || graphs[0]).uri)
    }
  }, [store.data, selectedGraph, onSelectGraph, config])

  useEffect(() => { if (!queryEdited) setQuery(starterQuery(selectedGraph)) }, [selectedGraph, queryEdited])

  const grouped = useMemo(() => catalog.reduce((groups, operation) => {
    (groups[operation.category] ||= []).push(operation)
    return groups
  }, {}), [catalog])
  const operation = catalog.find((item) => item.id === operationId)

  async function execute(task, label) {
    setRunning(true); setError(''); setOutcome(null)
    try {
      setOutcome({ ...(await task()), label })
    } catch (reason) {
      setError(reason.message)
    } finally {
      setRunning(false)
    }
  }

  const runOperation = (id, parameters) => execute(async () => {
    const value = await api.runOperation(id, parameters)
    return { query: value.query, result: value.result }
  }, operation?.title || id)

  const runQuery = () => execute(async () => ({ query, result: await api.query(query) }), 'SPARQL query')

  function openInEditor(text) {
    setQuery(text)
    setQueryEdited(true)
    setTab('sparql')
  }

  return (
    <div className="view">
      <div className="view-header">
        <div><p className="eyebrow">Query &amp; Agent</p><h1>Ask the knowledge graph</h1>
          <p className="lede">Run ready-made operations or write SPARQL against any graph in the triple store. No dataset upload needed.</p></div>
        <Badge tone="info"><Icon name="agent" size={14} /> Agent-ready API: GET /api/store/operations</Badge>
      </div>

      {!fusekiOnline && (
        <Notice tone="warning" title="Fuseki is offline">
          Start Apache Jena Fuseki with <code>./fuseki-server --update --mem /dataset</code>, then refresh the status in the sidebar.
        </Notice>
      )}

      <div className="query-layout">
        <GraphList store={store} config={config} selected={selectedGraph} onSelect={onSelectGraph} onRefresh={onRefreshStore} />

        <div className="stack">
          <Card padded={false}>
            <div className="tab-bar">
              <Segmented label="Query mode" value={tab} onChange={setTab} options={[
                { value: 'operations', label: 'Operations', icon: 'bolt' },
                { value: 'sparql', label: 'SPARQL editor', icon: 'code' },
              ]} />
              <span className="muted small">{tab === 'operations' ? 'Parameterised, read-only operations people and agents can reuse' : 'Read-only queries; select graphs with GRAPH <…>'}</span>
            </div>

            {tab === 'operations' ? (
              <div className="operations">
                {catalogError && <Notice tone="danger" title="Operations unavailable">{catalogError}</Notice>}
                <div className="operation-catalog">
                  {Object.entries(grouped).map(([category, items]) => (
                    <div key={category} className="operation-group">
                      <p className="eyebrow">{category}</p>
                      {items.map((item) => (
                        <button key={item.id} className={`operation-item ${item.id === operationId ? 'active' : ''}`} onClick={() => setOperationId(item.id)}>
                          <Icon name={OPERATION_ICONS[item.id] || 'bolt'} size={16} />
                          <span><strong>{item.title}</strong><small>{item.description}</small></span>
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
                {operation && <OperationForm key={operation.id} operation={operation} graph={selectedGraph} busy={running} onRun={runOperation} />}
              </div>
            ) : (
              <div className="sparql-panel">
                <div className="code-editor">
                  <textarea aria-label="SPARQL query" spellCheck="false" value={query}
                    onChange={(event) => { setQuery(event.target.value); setQueryEdited(true) }}
                    onKeyDown={(event) => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && query.trim()) runQuery() }} />
                  <span className="code-editor-meta">Ctrl+Enter to run</span>
                </div>
                <div className="button-row">
                  <Button icon="play" busy={running} disabled={!query.trim() || !fusekiOnline} onClick={runQuery}>Run query</Button>
                  <Button variant="ghost" icon="refresh" onClick={() => { setQueryEdited(false); setQuery(starterQuery(selectedGraph)) }}>Reset to starter query</Button>
                </div>
              </div>
            )}
          </Card>

          {(running || error || outcome) && (
            <Card title={outcome ? outcome.label : 'Results'} icon="table"
              actions={outcome?.query && tab === 'operations' && <Button variant="ghost" icon="code" onClick={() => openInEditor(outcome.query)}>Edit as SPARQL</Button>}>
              {running && <div className="loading-row"><Spinner /> Running against Fuseki</div>}
              {error && <Notice tone="danger" title="Query failed">{error}</Notice>}
              {outcome && (
                <>
                  {tab === 'operations' && (
                    <details className="log-details"><summary>Generated SPARQL</summary><pre>{outcome.query}</pre></details>
                  )}
                  <QueryResults result={outcome.result} filename={outcome.label.toLowerCase().replace(/\W+/g, '-')} />
                </>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
