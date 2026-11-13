import { useState } from 'react'
import { formatBytes, formatNumber } from '../format.js'
import { Badge, Button, Card, CopyButton, Icon, Kpi, Notice } from '../components/ui.jsx'

function UploadPanel({ onUpload, busy }) {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  return (
    <Card title="Upload a dataset" subtitle="Your file is stored in an isolated workspace on the server." icon="upload">
      <label className={`dropzone ${dragging ? 'dragging' : ''}`}
        onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); setFile(event.dataTransfer.files?.[0] || null) }}>
        <input type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(event) => setFile(event.target.files?.[0] || null)} />
        <Icon name={file ? 'file' : 'upload'} size={28} />
        <strong>{file ? file.name : 'Drop a CSV or Excel file here'}</strong>
        <span>{file ? `${formatBytes(file.size)} selected` : 'or click to browse · .csv and .xlsx · Excel uses the active sheet'}</span>
      </label>
      <div className="button-row">
        <Button icon="upload" busy={busy} disabled={!file} onClick={() => onUpload(file)}>Upload and preview</Button>
        {file && <Button variant="ghost" onClick={() => setFile(null)} disabled={busy}>Clear</Button>}
      </div>
    </Card>
  )
}

export default function DataView({ run, busy, onUpload, onDelete }) {
  const [confirming, setConfirming] = useState(false)
  const source = run?.source
  const preview = source?.preview

  if (!preview) {
    return (
      <div className="view">
        <div className="view-header"><div><p className="eyebrow">Data</p><h1>Bring your own data</h1>
          <p className="lede">Start from a spreadsheet. You can map it to RDF, check it, and publish it afterwards.</p></div></div>
        <UploadPanel onUpload={onUpload} busy={busy === 'upload'} />
      </div>
    )
  }

  return (
    <div className="view">
      <div className="view-header">
        <div><p className="eyebrow">Data</p><h1>{source.stored_filename}</h1>
          <p className="lede">Parsed preview of the active dataset. Column names are what your RML mapping references.</p></div>
        <div className="button-row">
          {!confirming && <Button variant="danger-ghost" icon="trash" onClick={() => setConfirming(true)}>Remove dataset</Button>}
        </div>
      </div>

      {confirming && (
        <Notice tone="warning" title="Remove this dataset and everything generated from it?">
          <p>The upload, RDF, reports, and downloads are deleted. Graphs already published to Fuseki stay in the triple store.</p>
          <div className="button-row">
            <Button variant="danger" icon="trash" busy={busy === 'delete'} onClick={onDelete}>Remove dataset</Button>
            <Button variant="ghost" onClick={() => setConfirming(false)}>Cancel</Button>
          </div>
        </Notice>
      )}

      <div className="kpi-grid">
        <Kpi label="Rows" icon="table" value={formatNumber(preview.total_rows)} hint={`Previewing ${preview.preview_row_count}`} />
        <Kpi label="Columns" icon="layers" value={formatNumber(preview.columns.length)} />
        <Kpi label="Format" icon="file" value={preview.format.toUpperCase()}
          hint={preview.sheet_name ? `Sheet: ${preview.sheet_name}` : `${preview.encoding} · delimiter ${preview.delimiter}`} />
        <Kpi label="File size" icon="download" value={formatBytes(preview.size)} />
      </div>

      <Card title="Mapping source" icon="mapping"
        subtitle={preview.format === 'xlsx' ? 'The active worksheet was converted to CSV for RMLMapper.' : 'Use this exact name as rml:source in your mapping.'}>
        <div className="source-name">
          <code>{source.mapping_source_filename}</code>
          <CopyButton text={source.mapping_source_filename} />
        </div>
        <div className="chip-row">
          {preview.columns.map((column) => <Badge key={column}>{column}</Badge>)}
        </div>
      </Card>

      <Card title="Preview" subtitle={`First ${preview.preview_row_count} of ${formatNumber(preview.total_rows)} rows`} icon="table" padded={false}>
        <div className="table-wrap tall">
          <table className="data-table">
            <thead><tr>{preview.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
            <tbody>
              {preview.rows.map((row, index) => (
                <tr key={index}>{preview.columns.map((column) => (
                  <td key={column} title={row[column]}>{row[column] || <em className="muted">empty</em>}</td>
                ))}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
