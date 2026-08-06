import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

const API = import.meta.env.VITE_PIPELINE_API_URL || 'http://localhost:8000'
const completedStatuses = new Set(['success', 'nonconformant'])

const stageDefinitions = [
  { id: 'upload', title: 'Upload tabular data', eyebrow: 'Data input', description: 'Upload a CSV file or Excel workbook and inspect a parsed preview before processing begins.' },
  { id: 'rml', title: 'Map data to RDF', eyebrow: 'RML mapping', description: 'Paste your RML mapping and run RMLMapper against the prepared CSV source.' },
  { id: 'ingest', title: 'Ingest into Fuseki', eyebrow: 'Triple store', description: 'Clear and replace the named graph with the mapped RDF.' },
  { id: 'shacl_in', title: 'Validate mapped RDF', eyebrow: 'SHACL in · Optional', description: 'Optionally run your input shape without stopping the pipeline when violations are found.' },
  { id: 'reason', title: 'Apply semantic rules', eyebrow: 'N3 reasoner · Optional', description: 'Optionally run user-provided N3 rules and materialise inferred RDF.' },
  { id: 'rdf2tss', title: 'Create TSS data', eyebrow: 'RDF2TSS', description: 'Transform compatible RDF observations with the existing RDF2TSS queries.' },
  { id: 'shacl_out', title: 'Validate TSS output', eyebrow: 'SHACL out · Optional', description: 'Optionally check the generated TSS graph against your output shape.' },
  { id: 'rdf2ldes', title: 'Generate and download LDES', eyebrow: 'RDF2LDES', description: 'Build the existing TREE/LDES hierarchy and download the complete folder as ZIP.' },
]

const stagePrerequisites = {
  upload: [],
  rml: ['upload'],
  ingest: ['rml'],
  shacl_in: ['rml'],
  reason: ['rml'],
  rdf2tss: ['rml'],
  shacl_out: ['rdf2tss'],
  rdf2ldes: ['rdf2tss'],
}

const defaultSparqlQuery = `SELECT ?subject ?predicate ?object
WHERE {
  GRAPH <https://example.org/graphs/your-graph> {
    ?subject ?predicate ?object .
  }
}
LIMIT 100`

const requestJson = async (path, options = {}) => {
  const response = await fetch(`${API}${path}`, options)
  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}.`
    try {
      const payload = await response.json()
      message = payload.detail || message
    } catch {
      message = await response.text() || message
    }
    throw new Error(message)
  }
  if (response.status === 204) return null
  return response.json()
}

function statusLabel(status, enabled) {
  if (!enabled && !status) return 'Locked'
  return {
    success: 'Complete', nonconformant: 'Review report', error: 'Needs attention', running: 'Running',
  }[status] || 'Ready'
}

function StatusPill({ status, enabled = true }) {
  const value = status || (enabled ? 'ready' : 'locked')
  return <span className={`status-pill ${value}`}><i />{statusLabel(status, enabled)}</span>
}

function CodeEditor({ id, label, value, onChange, placeholder, rows = 13 }) {
  const lineCount = value ? value.split('\n').length : 0
  return <div className="code-field">
    <div className="field-heading"><label htmlFor={id}>{label}</label><span>{lineCount} line{lineCount === 1 ? '' : 's'}</span></div>
    <textarea id={id} rows={rows} spellCheck="false" value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
  </div>
}

function ArtifactLinks({ artifacts, onPreview }) {
  if (!artifacts.length) return null
  return <div className="artifact-list">
    {artifacts.map((artifact) => artifact.kind === 'zip'
      ? <a className="artifact-button download" key={artifact.id} href={`${API}${artifact.download_url}`}><span>ZIP</span>{artifact.name}<b>Download</b></a>
      : <button className="artifact-button" key={artifact.id} onClick={() => onPreview(artifact)}><span>{artifact.kind.toUpperCase()}</span>{artifact.name}<b>Preview</b></button>)}
  </div>
}

function StageFeedback({ result, artifacts, onPreview }) {
  if (!result) return null
  return <div className={`stage-feedback ${result.status}`}>
    <div><strong>{result.message}</strong>{result.completed_at && <small>{new Date(result.completed_at).toLocaleString()}</small>}</div>
    {result.details?.report && <details open={result.status === 'nonconformant'}><summary>SHACL validation report</summary><pre>{result.details.report}</pre></details>}
    {result.log && <details><summary>Execution log</summary><pre>{result.log}</pre></details>}
    <ArtifactLinks artifacts={artifacts} onPreview={onPreview} />
  </div>
}

function StageCard({ number, definition, result, enabled, busy, artifacts, onRun, onPreview, children, actionLabel = 'Run stage' }) {
  return <article className={`pipeline-stage ${result?.status || (enabled ? 'ready' : 'locked')}`} id={`stage-${definition.id}`}>
    <div className="stage-index">{String(number).padStart(2, '0')}</div>
    <div className="stage-main">
      <div className="stage-title-row"><div><p className="eyebrow">{definition.eyebrow}</p><h2>{definition.title}</h2><p className="stage-description">{definition.description}</p></div><StatusPill status={result?.status} enabled={enabled} /></div>
      <div className="stage-controls">{children}</div>
      <div className="stage-actions"><button className="run-button" disabled={!enabled || busy} onClick={onRun}>{busy ? <><i className="spinner" />Running</> : actionLabel}</button>{!enabled && <span>Complete the required input stage to unlock this action.</span>}</div>
      <StageFeedback result={result} artifacts={artifacts} onPreview={onPreview} />
    </div>
  </article>
}

function DataPreview({ source }) {
  const preview = source?.preview
  if (!preview) return null
  return <div className="csv-preview">
    <div className="preview-meta"><div><strong>{source.stored_filename}</strong><span>{preview.total_rows.toLocaleString()} rows · {preview.columns.length} columns</span></div><div><span>{preview.format?.toUpperCase()}</span>{preview.sheet_name && <span>Sheet: {preview.sheet_name}</span>}{preview.encoding && <span>{preview.encoding}</span>}{preview.delimiter && <span>Delimiter: {preview.delimiter}</span>}<span>{(preview.size / 1024).toFixed(1)} KB</span></div></div>
    <div className="table-shell"><table><thead><tr>{preview.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.columns.map((column) => <td key={column} title={row[column]}>{row[column] || <em>empty</em>}</td>)}</tr>)}</tbody></table></div>
    <p className="preview-caption">Showing the first {preview.preview_row_count} parsed rows.</p>
  </div>
}

function ArtifactPreview({ artifact, onClose }) {
  const [content, setContent] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    requestJson(artifact.preview_url).then((value) => active && setContent(value)).catch((reason) => active && setError(reason.message))
    return () => { active = false }
  }, [artifact])
  return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="artifact-drawer" onMouseDown={(event) => event.stopPropagation()}>
    <div className="drawer-header"><div><p className="eyebrow">Artifact preview</p><h2>{artifact.name}</h2><span>{artifact.kind.toUpperCase()} · {artifact.size.toLocaleString()} bytes</span></div><button onClick={onClose} aria-label="Close preview">×</button></div>
    {error && <div className="notice error">{error}</div>}
    {!content && !error && <div className="drawer-loading"><i className="spinner" />Loading preview</div>}
    {content?.text && <pre className="source-preview">{content.text}</pre>}
    {content?.table && <DataPreview source={{ stored_filename: artifact.name, preview: content.table }} />}
    {content?.truncated && <p className="preview-caption">This preview was limited to 100,000 characters.</p>}
    <a className="drawer-download" href={`${API}${artifact.download_url}`}>Download artifact</a>
  </aside></div>
}

function UploadStage({ run, file, setFile, busy, deleting, onUpload, onDelete, onPreview }) {
  const definition = stageDefinitions[0]
  const result = run?.stages?.upload
  const artifacts = run?.artifacts?.filter((item) => item.stage === 'upload') || []
  const fileInput = useRef(null)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  useEffect(() => { setConfirmingDelete(false) }, [run?.id])
  const handleDrop = (event) => { event.preventDefault(); setFile(event.dataTransfer.files?.[0] || null) }
  const clearSelection = () => {
    setFile(null)
    if (fileInput.current) fileInput.current.value = ''
  }
  const fileType = file?.name.toLowerCase().endsWith('.xlsx') ? 'XLSX' : 'CSV'
  return <article className={`pipeline-stage ${result?.status || 'ready'}`} id="stage-upload">
    <div className="stage-index">01</div><div className="stage-main">
      <div className="stage-title-row"><div><p className="eyebrow">{definition.eyebrow}</p><h2>{definition.title}</h2><p className="stage-description">{definition.description}</p></div><StatusPill status={result?.status} /></div>
      {!run && <label className="drop-zone" onDrop={handleDrop} onDragOver={(event) => event.preventDefault()}>
        <input ref={fileInput} type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => setFile(event.target.files?.[0] || null)} />
        <span className="upload-mark">{fileType}</span><div><strong>{file ? file.name : 'Drop a CSV or XLSX file here'}</strong><p>{file ? `${(file.size / 1024).toFixed(1)} KB selected` : 'Excel workbooks use their active worksheet and are prepared as CSV for RMLMapper.'}</p></div><b>{file ? 'Change file' : 'Browse'}</b>
      </label>}
      {!run && <div className="stage-actions"><button className="run-button" disabled={!file || busy} onClick={onUpload}>{busy ? <><i className="spinner" />Uploading</> : 'Upload and preview'}</button>{file && <button className="secondary-button" disabled={busy} onClick={clearSelection}>Clear selection</button>}</div>}
      {run?.source?.preview && <DataPreview source={run.source} />}
      {run && !confirmingDelete && <div className="stage-actions upload-delete-actions"><button className="secondary-button danger-button" disabled={deleting} onClick={() => setConfirmingDelete(true)}>Delete file and start over</button><span>Clears this run so you can upload the correct CSV or XLSX file.</span></div>}
      {run && confirmingDelete && <div className="delete-confirmation"><div><strong>Delete this run&apos;s files?</strong><span>The upload and every generated artifact will be deleted. Data already ingested into Fuseki will remain.</span></div><div><button className="secondary-button danger-button" disabled={deleting} onClick={onDelete}>{deleting ? <><i className="spinner" />Deleting</> : 'Delete now'}</button><button className="secondary-button" disabled={deleting} onClick={() => setConfirmingDelete(false)}>Cancel</button></div></div>}
      <StageFeedback result={result} artifacts={artifacts} onPreview={onPreview} />
    </div>
  </article>
}

function SparqlWorkspace({ run, enabled }) {
  const [query, setQuery] = useState(defaultSparqlQuery)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setResult(null)
    setError('')
  }, [run?.id, run?.graph?.uri])

  async function executeQuery() {
    if (!run || !query.trim()) return
    setBusy(true); setError(''); setResult(null)
    try {
      setResult(await requestJson(`/api/runs/${run.id}/sparql`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      }))
    } catch (reason) {
      setError(reason.message)
    } finally {
      setBusy(false)
    }
  }

  const status = error ? 'error' : result ? 'success' : null
  const variables = result?.variables || []
  return <article className={`pipeline-stage query-workspace ${status || (enabled ? 'ready' : 'locked')}`} id="sparql-workspace">
    <div className="stage-index">Q</div>
    <div className="stage-main">
      <div className="stage-title-row"><div><p className="eyebrow">SPARQL workspace</p><h2>Query Fuseki</h2><p className="stage-description">Run a read-only SPARQL query and select each target named graph explicitly in the query.</p></div><StatusPill status={status} enabled={enabled} /></div>
      <div className="stage-controls">
        <div className="inline-tip"><strong>Available graph IRI</strong><code>{run?.graph?.uri || 'Ingest a graph first'}</code><span>No default graph is selected automatically. Add a GRAPH &lt;IRI&gt; clause to your query.</span></div>
        <CodeEditor id="sparql-editor" label="SPARQL query" value={query} onChange={setQuery} rows={10} placeholder="SELECT ?subject ?predicate ?object WHERE { GRAPH <https://example.org/graphs/your-graph> { ?subject ?predicate ?object } } LIMIT 100" />
      </div>
      <div className="stage-actions"><button className="run-button" disabled={!enabled || busy || !query.trim()} onClick={executeQuery}>{busy ? <><i className="spinner" />Querying</> : 'Run SPARQL query'}</button>{!enabled && <span>Ingest a named graph to unlock querying.</span>}</div>
      {error && <div className="query-message error"><strong>Query failed</strong><span>{error}</span></div>}
      {result?.type === 'ask' && <div className="query-message success"><strong>ASK result</strong><span>{result.boolean ? 'true' : 'false'}</span></div>}
      {result?.type === 'select' && <div className="query-results">
        <div className="query-summary"><strong>{result.row_count.toLocaleString()} result row{result.row_count === 1 ? '' : 's'}</strong><span>{result.truncated ? 'Results were capped by the server.' : 'Fuseki query completed.'}</span></div>
        <div className="table-shell"><table><thead><tr>{variables.map((variable) => <th key={variable}>?{variable}</th>)}</tr></thead><tbody>{result.rows.length ? result.rows.map((row, rowIndex) => <tr key={rowIndex}>{variables.map((variable) => { const term = row[variable]; return <td key={variable} title={term?.value || ''}>{term ? <><span>{term.value}</span><small>{term.type}{term.datatype ? ` · ${term.datatype}` : ''}{term['xml:lang'] ? ` · ${term['xml:lang']}` : ''}</small></> : <em>unbound</em>}</td> })}</tr>) : <tr><td colSpan={Math.max(variables.length, 1)}><em>No matching rows.</em></td></tr>}</tbody></table></div>
      </div>}
      {result?.type === 'graph' && <div className="query-results"><div className="query-summary"><strong>Graph result</strong><span>{result.content_type}{result.truncated ? ' · preview truncated' : ''}</span></div><pre className="source-preview">{result.text}</pre></div>}
    </div>
  </article>
}

function App() {
  const [run, setRun] = useState(null)
  const [config, setConfig] = useState(null)
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [previewArtifact, setPreviewArtifact] = useState(null)
  const [mapping, setMapping] = useState('')
  const [graphName, setGraphName] = useState('')
  const [shaclIn, setShaclIn] = useState('')
  const [rules, setRules] = useState('')
  const [shaclOut, setShaclOut] = useState('')
  const [streamName, setStreamName] = useState('dataset')
  const [baseUrl, setBaseUrl] = useState('https://example.org/ldes/')

  useEffect(() => { requestJson('/api/config').then(setConfig).catch((reason) => setError(reason.message)) }, [])

  const completed = useMemo(() => stageDefinitions.filter((stage) => completedStatuses.has(run?.stages?.[stage.id]?.status)).length, [run])
  const artifactMap = useMemo(() => new Map((run?.artifacts || []).map((artifact) => [artifact.id, artifact])), [run])
  const artifactsFor = (stage) => (run?.stages?.[stage]?.artifacts || []).map((id) => artifactMap.get(id)).filter(Boolean)
  const stageDone = (stage) => completedStatuses.has(run?.stages?.[stage]?.status)
  const stageEnabled = (stage) => (stagePrerequisites[stage] || []).every(stageDone)

  async function upload() {
    if (!file) return
    setBusy('upload'); setError('')
    const body = new FormData(); body.append('file', file)
    try { setRun(await requestJson('/api/runs', { method: 'POST', body })) }
    catch (reason) { setError(reason.message) }
    finally { setBusy('') }
  }

  async function execute(stage, body) {
    if (!run) return
    setBusy(stage); setError('')
    try {
      const options = { method: 'POST' }
      if (body !== undefined) { options.headers = { 'Content-Type': 'application/json' }; options.body = JSON.stringify(body) }
      setRun(await requestJson(`/api/runs/${run.id}/stages/${stage}`, options))
    } catch (reason) { setError(reason.message) }
    finally { setBusy('') }
  }

  function resetRun() {
    setRun(null); setFile(null); setMapping(''); setGraphName(''); setShaclIn(''); setRules(''); setShaclOut(''); setStreamName('dataset'); setError(''); setPreviewArtifact(null)
  }

  async function deleteUploadedFile() {
    if (!run) { setFile(null); return }
    setBusy('delete'); setError('')
    try {
      await requestJson(`/api/runs/${run.id}`, { method: 'DELETE' })
      resetRun()
    } catch (reason) { setError(reason.message) }
    finally { setBusy('') }
  }

  return <div className="app-shell">
    <aside className="pipeline-nav">
      <div className="brand"><span>S</span><div><strong>Semantic Studio</strong><small>Generic RDF pipeline</small></div></div>
      <div className="run-progress"><div><span>Pipeline progress</span><strong>{completed}/{stageDefinitions.length}</strong></div><div className="progress-track"><i style={{ width: `${completed / stageDefinitions.length * 100}%` }} /></div>{run ? <small>Run {run.id.slice(0, 8)}</small> : <small>No active run</small>}</div>
      <nav>{stageDefinitions.map((stage, index) => { const status = run?.stages?.[stage.id]?.status; const enabled = stageEnabled(stage.id); return <a key={stage.id} href={`#stage-${stage.id}`} className={status || ''}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{stage.title}</strong><small>{statusLabel(status, enabled)}</small></div></a> })}</nav>
      <div className="service-card"><span className={config?.fuseki?.connected ? 'online' : 'offline'}><i />{config?.fuseki?.connected ? 'Fuseki connected' : 'Fuseki unavailable'}</span><small>{config?.storage === 'run-scoped' ? 'Isolated run storage' : 'Checking services'}</small></div>
    </aside>

    <main className="workspace">
      <header className="workspace-header"><div><p className="eyebrow">Semantic data operations</p><h1>Build an RDF pipeline from your own data.</h1><p>Upload CSV or XLSX data, provide each semantic contract, and inspect every result from mapping through LDES packaging.</p></div></header>
      {error && <div className="notice error"><strong>Request failed</strong><span>{error}</span><button onClick={() => setError('')}>×</button></div>}
      <section className="system-strip"><div><span>API</span><strong>Connected</strong></div><div><span>Fuseki</span><strong className={config?.fuseki?.connected ? 'good' : 'warn'}>{config?.fuseki?.connected ? 'Connected' : 'Offline'}</strong></div><div><span>RMLMapper</span><strong className={config?.tools?.rml_mapper ? 'good' : 'warn'}>{config?.tools?.rml_mapper ? 'Ready' : 'Missing'}</strong></div><div><span>EYE reasoner</span><strong className={config?.tools?.eye ? 'good' : 'warn'}>{config?.tools?.eye ? 'Ready' : 'Missing'}</strong></div></section>

      <section className="pipeline-list">
        <UploadStage run={run} file={file} setFile={setFile} busy={busy === 'upload'} deleting={busy === 'delete'} onUpload={upload} onDelete={deleteUploadedFile} onPreview={setPreviewArtifact} />

        <StageCard number={2} definition={stageDefinitions[1]} result={run?.stages?.rml} enabled={stageEnabled('rml')} busy={busy === 'rml'} artifacts={artifactsFor('rml')} onPreview={setPreviewArtifact} onRun={() => execute('rml', { mapping })} actionLabel="Run RML mapping">
          <div className="inline-tip"><strong>RML source name</strong><code>{run?.source?.mapping_source_filename || 'Upload data first'}</code><span>Use this exact prepared CSV filename as the mapping&apos;s logical source.</span></div>
          <CodeEditor id="rml-editor" label="RML mapping (Turtle)" value={mapping} onChange={setMapping} placeholder={'@prefix rml: <http://w3id.org/rml/> .\n\n# Paste your complete RML mapping here.'} />
        </StageCard>

        <StageCard number={3} definition={stageDefinitions[2]} result={run?.stages?.ingest} enabled={stageEnabled('ingest')} busy={busy === 'ingest'} artifacts={artifactsFor('ingest')} onPreview={setPreviewArtifact} onRun={() => execute('ingest', { graph_name: graphName })} actionLabel="Ingest graph">
          <div className="form-field"><label htmlFor="graph-name">Named graph</label><input id="graph-name" value={graphName} onChange={(event) => setGraphName(event.target.value)} placeholder="products-2026 or https://example.org/graphs/products" /><small>Enter a short name or a complete graph IRI.</small></div>
          <div className="inline-tip"><strong>Replacement policy</strong><span>The named graph is cleared before every ingestion, then replaced with this run&apos;s mapped RDF.</span></div>
        </StageCard>

        <SparqlWorkspace run={run} enabled={stageDone('ingest')} />

        <StageCard number={4} definition={stageDefinitions[3]} result={run?.stages?.shacl_in} enabled={stageEnabled('shacl_in')} busy={busy === 'shacl-in'} artifacts={artifactsFor('shacl_in')} onPreview={setPreviewArtifact} onRun={() => execute('shacl-in', { shapes: shaclIn })} actionLabel="Validate mapped RDF">
          <CodeEditor id="shacl-in-editor" label="Input SHACL shape (Turtle)" value={shaclIn} onChange={setShaclIn} placeholder={'@prefix sh: <http://www.w3.org/ns/shacl#> .\n\n# Paste the shape for the mapped RDF here.'} />
        </StageCard>

        <StageCard number={5} definition={stageDefinitions[4]} result={run?.stages?.reason} enabled={stageEnabled('reason')} busy={busy === 'reason'} artifacts={artifactsFor('reason')} onPreview={setPreviewArtifact} onRun={() => execute('reason', { rules })} actionLabel="Run N3 reasoner">
          <CodeEditor id="n3-editor" label="N3 rules" value={rules} onChange={setRules} placeholder={'@prefix : <https://example.org/> .\n\n# Paste your N3 rules here.'} />
        </StageCard>

        <StageCard number={6} definition={stageDefinitions[5]} result={run?.stages?.rdf2tss} enabled={stageEnabled('rdf2tss')} busy={busy === 'rdf2tss'} artifacts={artifactsFor('rdf2tss')} onPreview={setPreviewArtifact} onRun={() => execute('rdf2tss')} actionLabel="Transform RDF to TSS">
          <div className="assumption-card"><span>Current compatibility contract</span><p>This stage uses reasoned RDF when Stage 5 completed successfully; otherwise it uses the mapped RDF directly. The selected input must contain the SOSA sensor, time, value, observed-property, and QUDT unit structure expected by the existing queries.</p></div>
        </StageCard>

        <StageCard number={7} definition={stageDefinitions[6]} result={run?.stages?.shacl_out} enabled={stageEnabled('shacl_out')} busy={busy === 'shacl-out'} artifacts={artifactsFor('shacl_out')} onPreview={setPreviewArtifact} onRun={() => execute('shacl-out', { shapes: shaclOut })} actionLabel="Validate TSS output">
          <CodeEditor id="shacl-out-editor" label="Output SHACL shape (Turtle)" value={shaclOut} onChange={setShaclOut} placeholder={'@prefix sh: <http://www.w3.org/ns/shacl#> .\n\n# Paste the shape for the generated TSS graph here.'} />
        </StageCard>

        <StageCard number={8} definition={stageDefinitions[7]} result={run?.stages?.rdf2ldes} enabled={stageEnabled('rdf2ldes')} busy={busy === 'rdf2ldes'} artifacts={artifactsFor('rdf2ldes')} onPreview={setPreviewArtifact} onRun={() => execute('rdf2ldes', { stream_name: streamName, base_url: baseUrl })} actionLabel="Generate LDES and ZIP">
          <div className="two-column"><div className="form-field"><label htmlFor="stream-name">Stream name</label><input id="stream-name" value={streamName} onChange={(event) => setStreamName(event.target.value)} placeholder="dataset" /></div><div className="form-field"><label htmlFor="base-url">Public base URL</label><input id="base-url" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://example.org/ldes/" /></div></div>
          <div className="assumption-card"><span>Current compatibility contract</span><p>RDF2LDES retains the existing TSS query and date-based TREE partitioning. The generated directory is packaged automatically after completion.</p></div>
        </StageCard>
      </section>
    </main>
    {previewArtifact && <ArtifactPreview artifact={previewArtifact} onClose={() => setPreviewArtifact(null)} />}
  </div>
}

export default App
