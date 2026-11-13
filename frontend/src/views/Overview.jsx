import { compactNumber, formatNumber, isDone, shortIri, timeAgo } from '../format.js'
import { Badge, Button, Card, EmptyState, Icon, Kpi } from '../components/ui.jsx'

const ACTIVITY = {
  upload: ['table', 'Dataset uploaded'],
  rml: ['mapping', 'RDF generated'],
  rules: ['sparkle', 'SHACL rules applied'],
  shacl: ['shield', 'Data validated'],
  ingest: ['database', 'Published to Fuseki'],
}

function QualityBreakdown({ shacl, onOpen }) {
  const counts = shacl?.details?.severity_counts
  if (!counts) return null
  const total = Object.values(counts).reduce((sum, value) => sum + value, 0)
  const rows = [['Violation', 'danger'], ['Warning', 'warning'], ['Info', 'info']]
  const byConstraint = {}
  for (const item of shacl.details.results || []) byConstraint[item.constraint] = (byConstraint[item.constraint] || 0) + 1
  const top = Object.entries(byConstraint).sort((a, b) => b[1] - a[1]).slice(0, 4)
  return (
    <Card title="Data quality" subtitle={total ? `${formatNumber(total)} findings from the latest validation` : 'The latest validation found no issues'}
      icon="shield" actions={<Button variant="ghost" icon="arrow" onClick={onOpen}>Details</Button>}>
      <div className="severity-bars">
        {rows.map(([name, tone]) => (
          <div key={name} className="severity-row">
            <span>{name === 'Info' ? 'Notes' : `${name}s`}</span>
            <div className="bar-track"><i className={`bar-${tone}`} style={{ width: `${total ? (counts[name] / total) * 100 : 0}%` }} /></div>
            <strong>{formatNumber(counts[name])}</strong>
          </div>
        ))}
      </div>
      {top.length > 0 && (
        <div className="chip-row">
          {top.map(([constraint, count]) => <Badge key={constraint}>{constraint} · {count}</Badge>)}
        </div>
      )}
    </Card>
  )
}

export default function Overview({ run, config, store, navigate }) {
  const fusekiOnline = Boolean(config?.fuseki?.connected)
  const source = run?.source
  const uploaded = isDone(run, 'upload')
  const mapped = isDone(run, 'rml')
  const rml = run?.stages?.rml
  const rules = run?.stages?.rules
  const shacl = run?.stages?.shacl
  const ingest = run?.stages?.ingest
  const triples = rules?.status === 'success' ? rules.details.total_triples : rml?.details?.rdf_triples
  const graphCount = store.data?.graphs?.length

  const qualityValue = !shacl ? 'Not checked'
    : shacl.status === 'success' ? 'Conforms'
      : shacl.status === 'nonconformant' ? `${formatNumber(shacl.details.severity_counts.Violation)} violations`
        : 'Check failed'
  const qualityTone = !shacl ? 'neutral' : shacl.status === 'success' ? 'success' : shacl.status === 'nonconformant' ? 'warning' : 'danger'

  const actions = [
    { view: 'data', icon: 'upload', title: uploaded ? 'Review dataset' : 'Upload a dataset', text: 'CSV or Excel files, previewed instantly.', done: uploaded },
    { view: 'mapping', icon: 'mapping', title: 'Map to RDF', text: 'Paste or upload an RML mapping.', done: mapped, locked: !uploaded },
    { view: 'quality', icon: 'shield', title: 'Check data quality', text: 'Validate with SHACL shapes and apply rules.', done: Boolean(shacl), locked: !mapped },
    { view: 'graph', icon: 'database', title: 'Download or publish', text: 'Export RDF or load it into Fuseki.', done: isDone(run, 'ingest'), locked: !mapped },
    { view: 'query', icon: 'agent', title: 'Query & Agent', text: 'Explore every graph in the triple store.', done: false, locked: false },
  ]

  const activity = Object.entries(run?.stages || {})
    .filter(([stage, result]) => ACTIVITY[stage] && result.completed_at)
    .sort((a, b) => b[1].completed_at.localeCompare(a[1].completed_at))

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <p className="eyebrow">Semantic Data Studio</p>
          <h1>{run ? `Working on ${source?.stored_filename}` : 'Turn spreadsheets into a trusted knowledge graph'}</h1>
          <p className="lede">Map tabular data to RDF, check its quality with SHACL, publish it to Fuseki, and query it in one place.</p>
        </div>
        {!run && <Button icon="upload" onClick={() => navigate('data')}>Upload a dataset</Button>}
      </div>

      <div className="kpi-grid">
        <Kpi label="Dataset" icon="table" onClick={() => navigate('data')}
          value={uploaded ? `${formatNumber(source.preview.total_rows)} rows` : 'No dataset'}
          hint={uploaded ? `${source.preview.columns.length} columns · ${source.preview.format.toUpperCase()}` : 'Upload CSV or XLSX'} />
        <Kpi label="RDF triples" icon="mapping" onClick={() => navigate(mapped ? 'graph' : 'mapping')}
          value={mapped ? compactNumber(triples) : '—'}
          hint={rules?.status === 'success' ? `incl. ${formatNumber(rules.details.inferred_triples)} inferred` : mapped ? 'From RML mapping' : 'Not mapped yet'} />
        <Kpi label="Data quality" icon="shield" tone={qualityTone} value={qualityValue} onClick={() => navigate('quality')}
          hint={shacl?.details?.severity_counts ? `${formatNumber(shacl.details.severity_counts.Warning)} warnings` : 'SHACL validation'} />
        <Kpi label="Published graph" icon="database" onClick={() => navigate('graph')}
          tone={isDone(run, 'ingest') ? 'success' : 'neutral'}
          value={isDone(run, 'ingest') ? shortIri(run.graph?.uri) : 'Not published'}
          hint={isDone(run, 'ingest') ? `${ingest.details.mode === 'append' ? 'Appended' : 'Replaced'} ${timeAgo(ingest.completed_at)}` : 'Fuseki named graph'} />
        <Kpi label="Triple store" icon="layers" onClick={() => navigate('query')}
          tone={fusekiOnline ? 'success' : 'danger'}
          value={fusekiOnline ? `${graphCount ?? '…'} graph${graphCount === 1 ? '' : 's'}` : 'Offline'}
          hint={fusekiOnline ? 'Apache Jena Fuseki' : 'Start Fuseki on port 3030'} />
      </div>

      <div className="overview-grid">
        <Card title="Quick actions" subtitle="Open any workspace. Each one tells you what it needs." icon="bolt">
          <div className="action-list">
            {actions.map((action) => (
              <button key={action.view} className={`action-item ${action.locked ? 'locked' : ''}`} onClick={() => navigate(action.view)}>
                <span className="action-icon"><Icon name={action.icon} size={20} /></span>
                <span className="action-text"><strong>{action.title}</strong><small>{action.locked ? 'Available after the earlier steps' : action.text}</small></span>
                {action.done ? <Badge tone="success" dot>Done</Badge> : <Icon name="arrow" size={16} className="action-arrow" />}
              </button>
            ))}
          </div>
        </Card>

        <div className="stack">
          <QualityBreakdown shacl={shacl?.details ? shacl : null} onOpen={() => navigate('quality')} />
          <Card title="Recent activity" icon="refresh">
            {activity.length ? (
              <ol className="timeline">
                {activity.map(([stage, result]) => (
                  <li key={stage} className={`timeline-item ${result.status}`}>
                    <span className="timeline-icon"><Icon name={ACTIVITY[stage][0]} size={14} /></span>
                    <div><strong>{ACTIVITY[stage][1]}</strong><p>{result.message}</p></div>
                    <time>{timeAgo(result.completed_at)}</time>
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState icon="refresh" title="No activity yet">Actions you take on a dataset appear here.</EmptyState>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
