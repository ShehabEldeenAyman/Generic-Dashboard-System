import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { datasetStem, formatNumber, isDone } from '../format.js'
import { Button, Card, CopyButton, EmptyState, Kpi, LinkButton, Notice, Segmented, Spinner, StageResult } from '../components/ui.jsx'

const FORMATS = [
  { value: 'turtle', label: 'Turtle' },
  { value: 'ntriples', label: 'N-Triples' },
  { value: 'jsonld', label: 'JSON-LD' },
  { value: 'xml', label: 'RDF/XML' },
]

function RdfBrowser({ run }) {
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const version = `${run.stages.rml?.completed_at}|${run.stages.rules?.completed_at}`

  useEffect(() => { setOffset(0) }, [version])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    api.rdfPreview(run.id, offset)
      .then((value) => active && setPage(value))
      .catch((reason) => active && setError(reason.message))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [run.id, offset, version])

  const first = page?.returned_instances ? page.offset + 1 : 0
  const last = (page?.offset || 0) + (page?.returned_instances || 0)
  return (
    <Card title="Browse RDF" icon="layers" subtitle={page ? `${formatNumber(page.total_instances)} entities · ${formatNumber(page.total_triples)} triples · ${page.source}` : 'Loading…'}>
      {error && <Notice tone="danger" title="Preview failed">{error}</Notice>}
      {loading && !page && <div className="loading-row"><Spinner /> Loading entities</div>}
      {page && (
        <>
          <pre className={`code-block ${loading ? 'dim' : ''}`}>{page.text || 'No RDF entities were produced.'}</pre>
          <div className="pager">
            <Button variant="secondary" disabled={!page.has_previous || loading} onClick={() => setOffset(Math.max(0, page.offset - page.limit))}>Previous</Button>
            <span>Entities {formatNumber(first)}–{formatNumber(last)} of {formatNumber(page.total_instances)}</span>
            <Button variant="secondary" disabled={!page.has_next || loading} onClick={() => setOffset(page.offset + page.returned_instances)}>Next</Button>
          </div>
        </>
      )}
    </Card>
  )
}

export default function GraphView({ run, config, busy, onRunStage, navigate, onQueryGraph }) {
  const [format, setFormat] = useState('turtle')
  const [graphName, setGraphName] = useState(() => datasetStem(run))
  const [mode, setMode] = useState('replace')
  const fusekiOnline = Boolean(config?.fuseki?.connected)
  const rules = run?.stages?.rules
  const ingest = run?.stages?.ingest

  if (!isDone(run, 'rml')) {
    return (
      <div className="view">
        <div className="view-header"><div><p className="eyebrow">Knowledge graph</p><h1>Download and publish RDF</h1></div></div>
        <Card><EmptyState icon="mapping" title="Generate RDF first"
          action={<button className="btn btn-primary" onClick={() => navigate(run ? 'mapping' : 'data')}>{run ? 'Go to Mapping' : 'Go to Data'}</button>}>
          Once your data is mapped, you can download it in several formats or publish it to Fuseki.
        </EmptyState></Card>
      </div>
    )
  }

  const enriched = rules?.status === 'success'
  const triples = enriched ? rules.details.total_triples : run.stages.rml.details.rdf_triples
  const graphBase = config?.default_graph_base || 'https://example.org/graphs/'
  const previewIri = /^https?:\/\//.test(graphName.trim())
    ? graphName.trim()
    : `${graphBase.replace(/\/$/, '')}/${encodeURIComponent(graphName.trim())}`

  return (
    <div className="view">
      <div className="view-header">
        <div><p className="eyebrow">Knowledge graph</p><h1>Download and publish RDF</h1>
          <p className="lede">The current RDF is the {enriched ? 'enriched data (mapping plus rule inferences)' : 'output of your mapping'}.</p></div>
      </div>

      <div className="kpi-grid">
        <Kpi label="Current RDF" icon="layers" value={enriched ? 'Enriched' : 'Mapped'} hint={enriched ? `${formatNumber(rules.details.inferred_triples)} inferred triples` : 'From RML mapping'} />
        <Kpi label="Triples" icon="mapping" value={formatNumber(triples)} />
        <Kpi label="Published graph" icon="database" tone={isDone(run, 'ingest') ? 'success' : 'neutral'}
          value={isDone(run, 'ingest') ? 'Live' : 'Not published'} hint={run.graph?.uri || 'Publish below'} />
      </div>

      <div className="split even">
        <Card title="Download RDF" icon="download" subtitle="Export the current RDF for other tools.">
          <Segmented label="RDF format" value={format} onChange={setFormat} options={FORMATS} />
          <div className="button-row">
            <LinkButton variant="primary" icon="download" href={api.rdfDownloadUrl(run.id, format)}>
              Download {FORMATS.find((item) => item.value === format).label}
            </LinkButton>
          </div>
        </Card>

        <Card title="Publish to Fuseki" icon="database" subtitle="Load the current RDF into a named graph of the triple store.">
          {!fusekiOnline && <Notice tone="warning" title="Fuseki is offline">Start Fuseki with a dataset named “dataset” on port 3030, then refresh the status in the sidebar.</Notice>}
          <div className="field">
            <label htmlFor="graph-name">Named graph</label>
            <input id="graph-name" value={graphName} onChange={(event) => setGraphName(event.target.value)} placeholder="sales-2026 or https://example.org/graphs/sales" />
            <p className="field-hint">Graph IRI: <code>{graphName.trim() ? previewIri : '—'}</code></p>
          </div>
          <div className="field">
            <span className="field-label">When the graph already exists</span>
            <Segmented label="Ingestion mode" value={mode} onChange={setMode} options={[
              { value: 'replace', label: 'Replace its content' },
              { value: 'append', label: 'Add to it' },
            ]} />
          </div>
          <div className="button-row">
            <Button icon="upload" busy={busy === 'ingest'} disabled={!fusekiOnline || !graphName.trim()}
              onClick={() => onRunStage('ingest', { graph_name: graphName.trim(), mode })}>Publish</Button>
          </div>
          <StageResult result={ingest}>
            {ingest?.status === 'success' && (
              <div className="source-name">
                <code>{ingest.details.graph_uri}</code>
                <CopyButton text={ingest.details.graph_uri} />
                <Button variant="secondary" icon="agent" onClick={() => onQueryGraph(ingest.details.graph_uri)}>Query this graph</Button>
              </div>
            )}
          </StageResult>
        </Card>
      </div>

      <RdfBrowser run={run} />
    </div>
  )
}
