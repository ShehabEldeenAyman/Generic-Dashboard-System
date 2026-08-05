import { useEffect, useMemo, useState } from 'react'
import './App.css'

const API = import.meta.env.VITE_PIPELINE_API_URL || 'http://localhost:8000'
const completedStatuses = new Set(['success', 'nonconformant'])

const stageDefinitions = [
  { id: 'upload', title: 'Upload CSV', eyebrow: 'Data input', description: 'Upload a CSV file and inspect a parsed preview before processing begins.' },
  { id: 'rml', title: 'Map CSV to RDF', eyebrow: 'RML mapping', description: 'Paste your RML mapping and run RMLMapper against the uploaded filename.' },
  { id: 'ingest', title: 'Ingest into Fuseki', eyebrow: 'Triple store', description: 'Publish the mapped RDF into the named graph you choose.' },
  { id: 'shacl_in', title: 'Validate mapped RDF', eyebrow: 'SHACL in', description: 'Run your input shape without stopping the pipeline when violations are found.' },
  { id: 'reason', title: 'Apply semantic rules', eyebrow: 'N3 reasoner', description: 'Run user-provided N3 rules and materialise the inferred RDF.' },
  { id: 'rdf2tss', title: 'Create TSS data', eyebrow: 'RDF2TSS', description: 'Transform compatible RDF observations with the existing RDF2TSS queries.' },
  { id: 'shacl_out', title: 'Validate TSS output', eyebrow: 'SHACL out', description: 'Check the generated TSS graph against your output shape.' },
  { id: 'rdf2ldes', title: 'Generate and download LDES', eyebrow: 'RDF2LDES', description: 'Build the existing TREE/LDES hierarchy and download the complete folder as ZIP.' },
]

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
      <div className="stage-actions"><button className="run-button" disabled={!enabled || busy} onClick={onRun}>{busy ? <><i className="spinner" />Running</> : actionLabel}</button>{!enabled && <span>Complete the preceding stage to unlock this action.</span>}</div>
      <StageFeedback result={result} artifacts={artifacts} onPreview={onPreview} />
    </div>
  </article>
}

function CsvPreview({ source }) {
  const preview = source?.preview
  if (!preview) return null
  return <div className="csv-preview">
    <div className="preview-meta"><div><strong>{source.stored_filename}</strong><span>{preview.total_rows.toLocaleString()} rows · {preview.columns.length} columns</span></div><div><span>{preview.encoding}</span><span>Delimiter: {preview.delimiter}</span><span>{(preview.size / 1024).toFixed(1)} KB</span></div></div>
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
    {content?.table && <CsvPreview source={{ stored_filename: artifact.name, preview: content.table }} />}
    {content?.truncated && <p className="preview-caption">This preview was limited to 100,000 characters.</p>}
    <a className="drawer-download" href={`${API}${artifact.download_url}`}>Download artifact</a>
  </aside></div>
}

function UploadStage({ run, file, setFile, busy, onUpload, onPreview }) {
  const definition = stageDefinitions[0]
  const result = run?.stages?.upload
  const artifacts = run?.artifacts?.filter((item) => item.stage === 'upload') || []
  const handleDrop = (event) => { event.preventDefault(); setFile(event.dataTransfer.files?.[0] || null) }
  return <article className={`pipeline-stage ${result?.status || 'ready'}`} id="stage-upload">
    <div className="stage-index">01</div><div className="stage-main">
      <div className="stage-title-row"><div><p className="eyebrow">{definition.eyebrow}</p><h2>{definition.title}</h2><p className="stage-description">{definition.description}</p></div><StatusPill status={result?.status} /></div>
      {!run && <label className="drop-zone" onDrop={handleDrop} onDragOver={(event) => event.preventDefault()}>
        <input type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] || null)} />
        <span className="upload-mark">CSV</span><div><strong>{file ? file.name : 'Drop a CSV here or choose a file'}</strong><p>{file ? `${(file.size / 1024).toFixed(1)} KB selected` : 'The server parses the header and returns a bounded preview.'}</p></div><b>{file ? 'Change file' : 'Browse'}</b>
      </label>}
      {!run && <div className="stage-actions"><button className="run-button" disabled={!file || busy} onClick={onUpload}>{busy ? <><i className="spinner" />Uploading</> : 'Upload and preview'}</button></div>}
      {run?.source?.preview && <CsvPreview source={run.source} />}
      <StageFeedback result={result} artifacts={artifacts} onPreview={onPreview} />
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
    setRun(null); setFile(null); setMapping(''); setGraphName(''); setShaclIn(''); setRules(''); setShaclOut(''); setStreamName('dataset'); setError('')
  }

  return <div className="app-shell">
    <aside className="pipeline-nav">
      <div className="brand"><span>S</span><div><strong>Semantic Studio</strong><small>Generic RDF pipeline</small></div></div>
      <div className="run-progress"><div><span>Pipeline progress</span><strong>{completed}/{stageDefinitions.length}</strong></div><div className="progress-track"><i style={{ width: `${completed / stageDefinitions.length * 100}%` }} /></div>{run ? <small>Run {run.id.slice(0, 8)}</small> : <small>No active run</small>}</div>
      <nav>{stageDefinitions.map((stage, index) => { const status = run?.stages?.[stage.id]?.status; const enabled = index === 0 || stageDone(stageDefinitions[index - 1].id); return <a key={stage.id} href={`#stage-${stage.id}`} className={status || ''}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{stage.title}</strong><small>{statusLabel(status, enabled)}</small></div></a> })}</nav>
      <div className="service-card"><span className={config?.fuseki?.connected ? 'online' : 'offline'}><i />{config?.fuseki?.connected ? 'Fuseki connected' : 'Fuseki unavailable'}</span><small>{config?.storage === 'run-scoped' ? 'Isolated run storage' : 'Checking services'}</small></div>
    </aside>

    <main className="workspace">
      <header className="workspace-header"><div><p className="eyebrow">Semantic data operations</p><h1>Build an RDF pipeline from your own data.</h1><p>Upload a CSV, provide each semantic contract, and inspect every result from mapping through LDES packaging.</p></div>{run && <button className="secondary-button" onClick={resetRun}>Start a new run</button>}</header>
      {error && <div className="notice error"><strong>Request failed</strong><span>{error}</span><button onClick={() => setError('')}>×</button></div>}
      <section className="system-strip"><div><span>API</span><strong>Connected</strong></div><div><span>Fuseki</span><strong className={config?.fuseki?.connected ? 'good' : 'warn'}>{config?.fuseki?.connected ? 'Connected' : 'Offline'}</strong></div><div><span>RMLMapper</span><strong className={config?.tools?.rml_mapper ? 'good' : 'warn'}>{config?.tools?.rml_mapper ? 'Ready' : 'Missing'}</strong></div><div><span>EYE reasoner</span><strong className={config?.tools?.eye ? 'good' : 'warn'}>{config?.tools?.eye ? 'Ready' : 'Missing'}</strong></div></section>

      <section className="pipeline-list">
        <UploadStage run={run} file={file} setFile={setFile} busy={busy === 'upload'} onUpload={upload} onPreview={setPreviewArtifact} />

        <StageCard number={2} definition={stageDefinitions[1]} result={run?.stages?.rml} enabled={stageDone('upload')} busy={busy === 'rml'} artifacts={artifactsFor('rml')} onPreview={setPreviewArtifact} onRun={() => execute('rml', { mapping })} actionLabel="Run RML mapping">
          <div className="inline-tip"><strong>CSV source name</strong><code>{run?.source?.stored_filename || 'Upload a CSV first'}</code><span>Use this exact filename as the mapping&apos;s logical source.</span></div>
          <CodeEditor id="rml-editor" label="RML mapping (Turtle)" value={mapping} onChange={setMapping} placeholder={'@prefix rml: <http://w3id.org/rml/> .\n\n# Paste your complete RML mapping here.'} />
        </StageCard>

        <StageCard number={3} definition={stageDefinitions[2]} result={run?.stages?.ingest} enabled={stageDone('rml')} busy={busy === 'ingest'} artifacts={artifactsFor('ingest')} onPreview={setPreviewArtifact} onRun={() => execute('ingest', { graph_name: graphName })} actionLabel="Ingest graph">
          <div className="form-field"><label htmlFor="graph-name">Named graph</label><input id="graph-name" value={graphName} onChange={(event) => setGraphName(event.target.value)} placeholder="products-2026 or https://example.org/graphs/products" /><small>Enter a short name or a complete graph IRI.</small></div>
        </StageCard>

        <StageCard number={4} definition={stageDefinitions[3]} result={run?.stages?.shacl_in} enabled={stageDone('ingest')} busy={busy === 'shacl-in'} artifacts={artifactsFor('shacl_in')} onPreview={setPreviewArtifact} onRun={() => execute('shacl-in', { shapes: shaclIn })} actionLabel="Validate mapped RDF">
          <CodeEditor id="shacl-in-editor" label="Input SHACL shape (Turtle)" value={shaclIn} onChange={setShaclIn} placeholder={'@prefix sh: <http://www.w3.org/ns/shacl#> .\n\n# Paste the shape for the mapped RDF here.'} />
        </StageCard>

        <StageCard number={5} definition={stageDefinitions[4]} result={run?.stages?.reason} enabled={stageDone('shacl_in')} busy={busy === 'reason'} artifacts={artifactsFor('reason')} onPreview={setPreviewArtifact} onRun={() => execute('reason', { rules })} actionLabel="Run N3 reasoner">
          <CodeEditor id="n3-editor" label="N3 rules" value={rules} onChange={setRules} placeholder={'@prefix : <https://example.org/> .\n\n# Paste your N3 rules here.'} />
        </StageCard>

        <StageCard number={6} definition={stageDefinitions[5]} result={run?.stages?.rdf2tss} enabled={stageDone('reason')} busy={busy === 'rdf2tss'} artifacts={artifactsFor('rdf2tss')} onPreview={setPreviewArtifact} onRun={() => execute('rdf2tss')} actionLabel="Transform RDF to TSS">
          <div className="assumption-card"><span>Current compatibility contract</span><p>This stage intentionally retains the existing SPARQL queries. The reasoned RDF must contain the SOSA sensor, time, value, observed-property, and QUDT unit structure those queries expect.</p></div>
        </StageCard>

        <StageCard number={7} definition={stageDefinitions[6]} result={run?.stages?.shacl_out} enabled={stageDone('rdf2tss')} busy={busy === 'shacl-out'} artifacts={artifactsFor('shacl_out')} onPreview={setPreviewArtifact} onRun={() => execute('shacl-out', { shapes: shaclOut })} actionLabel="Validate TSS output">
          <CodeEditor id="shacl-out-editor" label="Output SHACL shape (Turtle)" value={shaclOut} onChange={setShaclOut} placeholder={'@prefix sh: <http://www.w3.org/ns/shacl#> .\n\n# Paste the shape for the generated TSS graph here.'} />
        </StageCard>

        <StageCard number={8} definition={stageDefinitions[7]} result={run?.stages?.rdf2ldes} enabled={stageDone('shacl_out')} busy={busy === 'rdf2ldes'} artifacts={artifactsFor('rdf2ldes')} onPreview={setPreviewArtifact} onRun={() => execute('rdf2ldes', { stream_name: streamName, base_url: baseUrl })} actionLabel="Generate LDES and ZIP">
          <div className="two-column"><div className="form-field"><label htmlFor="stream-name">Stream name</label><input id="stream-name" value={streamName} onChange={(event) => setStreamName(event.target.value)} placeholder="dataset" /></div><div className="form-field"><label htmlFor="base-url">Public base URL</label><input id="base-url" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://example.org/ldes/" /></div></div>
          <div className="assumption-card"><span>Current compatibility contract</span><p>RDF2LDES retains the existing TSS query and date-based TREE partitioning. The generated directory is packaged automatically after completion.</p></div>
        </StageCard>
      </section>
    </main>
    {previewArtifact && <ArtifactPreview artifact={previewArtifact} onClose={() => setPreviewArtifact(null)} />}
  </div>
}

export default App
