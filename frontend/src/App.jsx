import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { api } from './api.js'
import { formatNumber, isDone } from './format.js'
import { Button, Icon, Notice } from './components/ui.jsx'
import Overview from './views/Overview.jsx'
import DataView from './views/DataView.jsx'
import MappingView from './views/MappingView.jsx'
import QualityView from './views/QualityView.jsx'
import GraphView from './views/GraphView.jsx'
import QueryView from './views/QueryView.jsx'

const NAV = [
  { id: 'overview', label: 'Overview', icon: 'home' },
  { id: 'data', label: 'Data', icon: 'table' },
  { id: 'mapping', label: 'Mapping', icon: 'mapping' },
  { id: 'quality', label: 'Data quality', icon: 'shield' },
  { id: 'graph', label: 'Knowledge graph', icon: 'database' },
  { id: 'query', label: 'Query & Agent', icon: 'agent' },
]
const VIEW_IDS = new Set(NAV.map((item) => item.id))
const RUN_KEY = 'semantic-data-studio.dataset'

const storage = {
  get: () => { try { return localStorage.getItem(RUN_KEY) } catch { return null } },
  set: (value) => { try { localStorage.setItem(RUN_KEY, value) } catch { /* storage unavailable */ } },
  clear: () => { try { localStorage.removeItem(RUN_KEY) } catch { /* storage unavailable */ } },
}

const viewFromHash = () => {
  const id = window.location.hash.replace(/^#\/?/, '')
  return VIEW_IDS.has(id) ? id : 'overview'
}

function navStatus(run, id) {
  if (!run) return null
  const stage = { data: 'upload', mapping: 'rml', quality: 'shacl', graph: 'ingest' }[id]
  const result = run.stages?.[stage]
  if (!result) return null
  if (result.status === 'error') return 'danger'
  if (result.status === 'nonconformant') return 'warning'
  return result.status === 'success' ? 'success' : null
}

export default function App() {
  const [view, setView] = useState(viewFromHash)
  const [config, setConfig] = useState(null)
  const [run, setRun] = useState(null)
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState(null)
  const [store, setStore] = useState({ data: null, loading: false, error: '' })
  const [selectedGraph, setSelectedGraph] = useState('')

  const navigate = useCallback((id) => {
    window.location.hash = `/${id}`
  }, [])

  useEffect(() => {
    const onHash = () => { setView(viewFromHash()); window.scrollTo({ top: 0 }) }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const refreshConfig = useCallback(() => {
    api.config().then(setConfig).catch((reason) => setNotice({ tone: 'danger', title: 'The API is not reachable', text: reason.message }))
  }, [])

  const refreshStore = useCallback(() => {
    setStore((current) => ({ ...current, loading: true }))
    api.storeGraphs()
      .then((data) => setStore({ data, loading: false, error: '' }))
      .catch((reason) => setStore((current) => ({ ...current, loading: false, error: reason.message })))
  }, [])

  useEffect(() => { refreshConfig() }, [refreshConfig])
  useEffect(() => { if (config?.fuseki?.connected) refreshStore() }, [config, refreshStore])

  useEffect(() => {
    const saved = storage.get()
    if (!saved) return
    api.getRun(saved)
      .then((value) => (value.stages?.upload?.status === 'success' ? setRun(value) : storage.clear()))
      .catch(() => storage.clear())
  }, [])

  async function upload(file) {
    setBusy('upload'); setNotice(null)
    try {
      const result = await api.upload(file)
      if (result.stages?.upload?.status !== 'success') {
        setNotice({ tone: 'danger', title: 'The file could not be used', text: result.stages?.upload?.message })
        api.deleteRun(result.id).catch(() => {})
        return
      }
      setRun(result)
      storage.set(result.id)
    } catch (reason) {
      setNotice({ tone: 'danger', title: 'Upload failed', text: reason.message })
    } finally {
      setBusy('')
    }
  }

  async function removeDataset() {
    if (!run) return
    setBusy('delete'); setNotice(null)
    try {
      await api.deleteRun(run.id)
    } catch (reason) {
      if (reason.status !== 404) {
        setNotice({ tone: 'danger', title: 'The dataset could not be removed', text: reason.message })
        setBusy('')
        return
      }
    }
    setRun(null)
    storage.clear()
    setBusy('')
  }

  async function runStage(stage, body) {
    if (!run) return
    setBusy(stage); setNotice(null)
    try {
      const result = await api.runStage(run.id, stage, body)
      setRun(result)
      if (stage === 'ingest' && result.stages?.ingest?.status === 'success') refreshStore()
    } catch (reason) {
      setNotice({ tone: 'danger', title: 'The action could not start', text: reason.message })
    } finally {
      setBusy('')
    }
  }

  function queryGraph(uri) {
    setSelectedGraph(uri)
    navigate('query')
  }

  const artifactsFor = (stage) => {
    const ids = run?.stages?.[stage]?.artifacts || []
    return (run?.artifacts || []).filter((artifact) => ids.includes(artifact.id))
  }

  const datasetKey = run?.id || 'none'
  const shared = { run, config, busy, navigate, onRunStage: runStage }
  const fusekiOnline = Boolean(config?.fuseki?.connected)

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><Icon name="layers" size={18} /></span>
          <div><strong>Semantic Data Studio</strong><small>RDF · SHACL · SPARQL</small></div>
        </div>

        <nav className="nav" aria-label="Workspaces">
          {NAV.map((item) => {
            const status = navStatus(run, item.id)
            return (
              <a key={item.id} href={`#/${item.id}`} className={`nav-item ${view === item.id ? 'active' : ''}`}
                title={item.label} aria-label={item.label} aria-current={view === item.id ? 'page' : undefined}>
                <Icon name={item.icon} size={18} />
                <span>{item.label}</span>
                {status && <i className={`nav-dot ${status}`} aria-hidden="true" />}
              </a>
            )
          })}
        </nav>

        <div className="sidebar-foot">
          <div className="dataset-chip">
            <span className="muted small">Active dataset</span>
            {run ? (
              <>
                <strong title={run.source?.stored_filename}>{run.source?.stored_filename}</strong>
                <small>{formatNumber(run.source?.preview?.total_rows)} rows · {isDone(run, 'rml') ? 'mapped' : 'not mapped'}</small>
              </>
            ) : <strong className="muted">None</strong>}
          </div>
          <div className="service-list">
            <div className="service-head">
              <span className="muted small">Services</span>
              <button className="icon-button" onClick={refreshConfig} aria-label="Refresh service status"><Icon name="refresh" size={14} /></button>
            </div>
            <div className={`service ${fusekiOnline ? 'ok' : 'down'}`}><i />Fuseki<span>{fusekiOnline ? 'Connected' : 'Offline'}</span></div>
            <div className={`service ${config?.tools?.rml_mapper ? 'ok' : 'down'}`}><i />RMLMapper<span>{config?.tools?.rml_mapper ? 'Ready' : 'Missing'}</span></div>
            <div className={`service ${config?.tools?.java ? 'ok' : 'down'}`}><i />Java<span>{config?.tools?.java ? 'Found' : 'Missing'}</span></div>
          </div>
        </div>
      </aside>

      <main className="main">
        {notice && (
          <div className="toast-area">
            <Notice tone={notice.tone} title={notice.title} onClose={() => setNotice(null)}>{notice.text}</Notice>
          </div>
        )}
        <div hidden={view !== 'overview'}><Overview run={run} config={config} store={store} navigate={navigate} /></div>
        <div hidden={view !== 'data'}><DataView key={datasetKey} run={run} config={config} busy={busy} onUpload={upload} onDelete={removeDataset} /></div>
        <div hidden={view !== 'mapping'}><MappingView key={datasetKey} {...shared} /></div>
        <div hidden={view !== 'quality'}><QualityView key={datasetKey} {...shared} artifactsFor={artifactsFor} /></div>
        <div hidden={view !== 'graph'}><GraphView key={datasetKey} {...shared} onQueryGraph={queryGraph} /></div>
        <div hidden={view !== 'query'}>
          <QueryView config={config} store={store} onRefreshStore={refreshStore} active={view === 'query'}
            selectedGraph={selectedGraph} onSelectGraph={setSelectedGraph} />
        </div>
        {!config && !notice && <div className="boot"><Button variant="ghost" busy>Connecting to the API</Button></div>}
      </main>
    </div>
  )
}
