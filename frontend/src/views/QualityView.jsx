import { useMemo, useState } from 'react'
import { apiUrl } from '../api.js'
import { emptySource, formatNumber, isDone, shortIri } from '../format.js'
import SourceInput from '../components/SourceInput.jsx'
import { Badge, Button, Card, EmptyState, Icon, Kpi, LinkButton, Segmented, StageResult } from '../components/ui.jsx'

const PLACEHOLDER = `@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <https://example.org/> .

ex:ItemShape a sh:NodeShape ;
  sh:targetClass ex:Item ;
  sh:property [ sh:path ex:name ; sh:minCount 1 ; sh:message "Every item needs a name." ] .`

const SEVERITY_TONE = { Violation: 'danger', Warning: 'warning', Info: 'info' }

const plural = (count, noun) => `${count} ${noun}${count === 1 ? '' : 's'}`

function ShapesSummary({ shapes }) {
  if (!shapes) return null
  return (
    <div className="chip-row">
      <Badge>{plural(shapes.node_shapes, 'node shape')}</Badge>
      <Badge>{plural(shapes.property_shapes, 'property shape')}</Badge>
      <Badge>{plural(shapes.sparql_constraints, 'SPARQL constraint')}</Badge>
      <Badge tone={shapes.rules ? 'info' : 'neutral'}>{plural(shapes.rules, 'rule')}</Badge>
    </div>
  )
}

function ValidationResults({ result, artifacts }) {
  const [severity, setSeverity] = useState('all')
  const [search, setSearch] = useState('')
  const details = result.details
  const counts = details.severity_counts
  const rows = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return (details.results || []).filter((item) => (severity === 'all' || item.severity === severity) && (!needle
      || [item.focus_node, item.path, item.value, item.message, item.constraint].some((field) => field?.toLowerCase().includes(needle))))
  }, [details.results, severity, search])
  const report = artifacts.find((artifact) => artifact.kind === 'txt')

  return (
    <>
      <div className="kpi-grid compact">
        <Kpi label="Result" tone={details.conforms ? 'success' : 'warning'} value={details.conforms ? 'Conforms' : 'Issues found'}
          hint={`${formatNumber(details.data_triples)} triples checked (${details.input_rdf})`} />
        <Kpi label="Violations" tone={counts.Violation ? 'danger' : 'neutral'} value={formatNumber(counts.Violation)} />
        <Kpi label="Warnings" tone={counts.Warning ? 'warning' : 'neutral'} value={formatNumber(counts.Warning)} />
        <Kpi label="Notes" value={formatNumber(counts.Info)} hint={`${details.duration_seconds}s`} />
      </div>
      <ShapesSummary shapes={details.shapes} />
      {details.total_results > 0 && (
        <div className="results-panel">
          <div className="results-bar">
            <Segmented label="Filter by severity" value={severity} onChange={setSeverity} options={[
              { value: 'all', label: `All (${details.total_results})` },
              { value: 'Violation', label: 'Violations' },
              { value: 'Warning', label: 'Warnings' },
              { value: 'Info', label: 'Notes' },
            ]} />
            <label className="search-field">
              <Icon name="search" size={15} />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search results" />
            </label>
          </div>
          <div className="table-wrap tall">
            <table className="data-table">
              <thead><tr><th>Severity</th><th>Record</th><th>Property</th><th>Value</th><th>Message</th><th>Constraint</th></tr></thead>
              <tbody>
                {rows.length ? rows.map((item, index) => (
                  <tr key={index}>
                    <td><Badge tone={SEVERITY_TONE[item.severity] || 'neutral'}>{item.severity}</Badge></td>
                    <td title={item.focus_node}>{shortIri(item.focus_node)}</td>
                    <td title={item.path || ''}>{item.path ? shortIri(item.path) : <em className="muted">—</em>}</td>
                    <td title={item.value || ''}>{item.value ? shortIri(item.value) : <em className="muted">—</em>}</td>
                    <td className="wrap">{item.message || <em className="muted">No message</em>}</td>
                    <td>{item.constraint}</td>
                  </tr>
                )) : <tr><td colSpan="6" className="table-empty">No results match the filter.</td></tr>}
              </tbody>
            </table>
          </div>
          {details.truncated && <p className="muted small">Showing the first {formatNumber(details.results.length)} findings. Download the full report for all of them.</p>}
        </div>
      )}
      {report && <div className="button-row"><LinkButton icon="download" href={apiUrl(report.download_url)}>Full validation report</LinkButton></div>}
    </>
  )
}

export default function QualityView({ run, busy, onRunStage, navigate, artifactsFor }) {
  const [shapes, setShapes] = useState(emptySource)
  const validation = run?.stages?.shacl
  const rules = run?.stages?.rules

  if (!isDone(run, 'rml')) {
    return (
      <div className="view">
        <div className="view-header"><div><p className="eyebrow">Data quality</p><h1>Check and enrich your data</h1></div></div>
        <Card><EmptyState icon="mapping" title="Generate RDF first"
          action={<button className="btn btn-primary" onClick={() => navigate(run ? 'mapping' : 'data')}>{run ? 'Go to Mapping' : 'Go to Data'}</button>}>
          SHACL shapes and rules run on the RDF produced by your mapping.
        </EmptyState></Card>
      </div>
    )
  }

  const body = { shapes: shapes.text, source_name: shapes.mode === 'file' ? shapes.fileName : null }
  const enriched = rules?.status === 'success'

  return (
    <div className="view">
      <div className="view-header">
        <div><p className="eyebrow">Data quality</p><h1>Check and enrich your data</h1>
          <p className="lede">SHACL shapes describe what good data looks like. Validate against them, or run their rules to add inferred facts.</p></div>
      </div>

      <div className="split">
        <Card title="SHACL shapes and rules" icon="shield" subtitle="One shapes graph can hold constraints (sh:property, sh:sparql) and rules (sh:rule).">
          <SourceInput id="shacl-source" label="Shapes (Turtle)" value={shapes} onChange={setShapes}
            accept=".ttl,.shacl,.txt" placeholder={PLACEHOLDER} />
          <div className="button-row">
            <Button icon="shield" busy={busy === 'shacl'} disabled={!shapes.text.trim() || Boolean(busy)}
              onClick={() => onRunStage('shacl', body)}>Validate data</Button>
            <Button variant="secondary" icon="sparkle" busy={busy === 'shacl-rules'} disabled={!shapes.text.trim() || Boolean(busy)}
              onClick={() => onRunStage('shacl-rules', body)}>Apply rules</Button>
          </div>
        </Card>
        <div className="stack">
          <Card title="Data being checked" icon="database">
            <div className="fact-list">
              <div><span>Source</span><strong>{enriched ? 'Enriched RDF' : 'Mapped RDF'}</strong></div>
              <div><span>Triples</span><strong>{formatNumber(enriched ? rules.details.total_triples : run.stages.rml.details.rdf_triples)}</strong></div>
            </div>
            <p className="muted small">{enriched
              ? 'Rule inferences are included in validation, downloads, and publishing.'
              : 'Validation checks the data as it is. Apply rules first if your constraints depend on inferred facts.'}</p>
          </Card>
          <Card title="What is supported" icon="info">
            <ul className="plain-list">
              <li>SHACL Core constraints: cardinality, datatypes, values, patterns</li>
              <li>SPARQL-based constraints (<code>sh:sparql</code>)</li>
              <li>Triple and SPARQL rules (<code>sh:TripleRule</code>, <code>sh:SPARQLRule</code>), applied once in <code>sh:order</code></li>
              <li>Large datasets: SPARQL constraints and rules run per record, so they take longest</li>
            </ul>
          </Card>
        </div>
      </div>

      {rules && (
        <Card title="Rules" icon="sparkle">
          <StageResult result={rules}>
            {rules.status === 'success' && (
              <>
                <div className="kpi-grid compact">
                  <Kpi label="Inferred triples" tone="success" value={formatNumber(rules.details.inferred_triples)} />
                  <Kpi label="Total triples" value={formatNumber(rules.details.total_triples)} hint={`from ${formatNumber(rules.details.input_triples)} mapped`} />
                  <Kpi label="Rules in shapes" value={formatNumber(rules.details.shapes.rules)} hint={rules.details.shapes_source} />
                </div>
                <div className="button-row"><Button variant="secondary" icon="database" onClick={() => navigate('graph')}>Download or publish enriched RDF</Button></div>
              </>
            )}
          </StageResult>
        </Card>
      )}

      {validation && (
        <Card title="Validation" icon="shield">
          <StageResult result={validation}>
            {validation.details?.severity_counts && (
              <ValidationResults key={validation.completed_at} result={validation} artifacts={artifactsFor('shacl')} />
            )}
          </StageResult>
        </Card>
      )}
    </div>
  )
}
