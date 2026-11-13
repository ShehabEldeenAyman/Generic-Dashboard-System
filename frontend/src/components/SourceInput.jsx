import { useRef, useState } from 'react'
import { emptySource, formatBytes } from '../format.js'
import { Button, Icon, Segmented } from './ui.jsx'

const MAX_SOURCE_BYTES = 2_000_000

/** A semantic contract (RML mapping, SHACL shapes) given as pasted text or an uploaded file. */
export default function SourceInput({ id, label, value, onChange, accept = '.ttl,.txt', placeholder, hint }) {
  const fileInput = useRef(null)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  async function readFile(file) {
    setError('')
    if (!file) return
    if (file.size > MAX_SOURCE_BYTES) {
      setError(`${file.name} is ${formatBytes(file.size)}. The limit is 2 MB.`)
      return
    }
    try {
      const text = await file.text()
      onChange({ mode: 'file', text, fileName: file.name, fileSize: file.size })
    } catch {
      setError(`${file.name} could not be read as text.`)
    }
  }

  function switchMode(mode) {
    setError('')
    if (mode === value.mode) return
    // Keep pasted text when switching to the editor so uploaded content can be edited.
    onChange(mode === 'paste'
      ? { ...emptySource, text: value.text }
      : { ...emptySource, mode: 'file' })
  }

  const lines = value.text ? value.text.split('\n').length : 0

  return (
    <div className="source-input">
      <div className="source-input-head">
        <label htmlFor={id}>{label}</label>
        <Segmented label={`${label} input method`} value={value.mode} onChange={switchMode} options={[
          { value: 'paste', label: 'Paste code', icon: 'code' },
          { value: 'file', label: 'Upload file', icon: 'upload' },
        ]} />
      </div>

      {value.mode === 'paste' ? (
        <div className="code-editor">
          <textarea id={id} spellCheck="false" value={value.text} placeholder={placeholder}
            onChange={(event) => onChange({ ...emptySource, text: event.target.value })} />
          <span className="code-editor-meta">{lines} line{lines === 1 ? '' : 's'}</span>
        </div>
      ) : value.fileName ? (
        <div className="file-card">
          <span className="file-card-icon"><Icon name="file" size={20} /></span>
          <div className="file-card-text">
            <strong>{value.fileName}</strong>
            <span>{formatBytes(value.fileSize)} · {lines} lines</span>
          </div>
          <Button variant="ghost" icon="code" onClick={() => onChange({ ...emptySource, text: value.text })}>Edit as text</Button>
          <Button variant="ghost" icon="refresh" onClick={() => fileInput.current?.click()}>Replace</Button>
          <input ref={fileInput} type="file" accept={accept} hidden onChange={(event) => readFile(event.target.files?.[0])} />
          <details className="file-card-preview">
            <summary>View contents</summary>
            <pre>{value.text.slice(0, 20_000)}{value.text.length > 20_000 ? '\n…' : ''}</pre>
          </details>
        </div>
      ) : (
        <label className={`dropzone compact ${dragging ? 'dragging' : ''}`}
          onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => { event.preventDefault(); setDragging(false); readFile(event.dataTransfer.files?.[0]) }}>
          <input id={id} type="file" accept={accept} onChange={(event) => readFile(event.target.files?.[0])} />
          <Icon name="upload" size={22} />
          <strong>Drop a file here or browse</strong>
          <span>Turtle files ({accept.replaceAll(',', ', ')}), up to 2 MB</span>
        </label>
      )}
      {hint && <p className="field-hint">{hint}</p>}
      {error && <p className="field-error">{error}</p>}
    </div>
  )
}
