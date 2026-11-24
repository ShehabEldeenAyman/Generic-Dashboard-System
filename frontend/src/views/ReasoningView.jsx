import { useEffect, useState } from 'react'
import { api, apiUrl } from '../api.js'
import { compactNumber, emptySource, formatNumber, isDone, shortIri } from '../format.js'
import SourceInput from '../components/SourceInput.jsx'
import { Badge, Button, Card, EmptyState, Kpi, LinkButton, Notice, Spinner, StageResult } from '../components/ui.jsx'

const PLACEHOLDER = `@prefix sosa: <http://www.w3.org/ns/sosa/> .

# If something made an observation, it is a sensor.
{ ?observation sosa:madeBySensor ?sensor } => { ?sensor a sosa:Sensor } .`

function Term({ term }) {
  if (term.type === 'iri') return <span className="term-iri" title={term.value}>{shortIri(term.value)}</span>
  if (term.type === 'blank') return <em className="muted" title={term.value}>blank node</em>
  return (
    <span title={term.datatype ? `${term.value} (${shortIri(term.datatype)})` : term.value}>
      {term.value}
      {term.language && <small className="term-lang">@{term.language}</small>}
    </span>
  )
}

function Breakdown({ title, items, total, empty }) {
  const largest = Math.max(1, ...items.map((item) => item.count))
  return (
    <div className="breakdown">
      <div className="breakdown-head">
        <strong>{title}</strong>
        {total > items.length && <span className="muted small">Top {items.length} of {total}</span>}
      </div>
      {items.length ? (
        <ul className="breakdown-list">
          {items.map((item) => (
            <li key={item.iri}>
              <span className="term-iri" title={item.iri}>{shortIri(item.iri)}</span>
              <div className="bar-track"><i className="bar-primary" style={{ width: `${(item.count / largest) * 100}%` }} /></div>
              <strong>{formatNumber(item.count)}</strong>
            </li>
          ))}
        </ul>
      ) : <p className="muted small">{empty}</p>}
    </div>
  )
}

function Inferences({ result, artifacts, navigate }) {
  const details = result.details
  const summary = details.summary
  const inferredFile = artifacts.find((artifact) => artifact.name === 'Inferred triples')
  const build = details.engine === 'native' ? 'Native' : 'Bundled'
  return (
    <>
      <div className="kpi-grid compact">
        <Kpi label="New triples" tone={details.inferred_triples ? 'success' : 'neutral'} value={formatNumber(details.inferred_triples)}
          hint={details.output_mode === 'query' ? 'Answers to the log:query' : 'Everything the rules derived'} />
        <Kpi label="Total triples" value={formatNumber(details.total_triples)}
          hint={`from ${formatNumber(details.input_triples)} in the ${details.input_rdf}`} />
        <Kpi label="Run time" value={`${details.duration_seconds}s`}
          hint={`${build} ${details.eye_version ? details.eye_version.replace(/ \(.*\)$/, '') : 'EYE'}`} />
        <Kpi label="Logical inferences" value={compactNumber(details.eye_stats?.inferences)} hint={`Rules: ${details.rules_source}`} />
      </div>

      {details.skipped_statements > 0 && (
        <Notice tone="info" title={`${formatNumber(details.skipped_statements)} N3-only statements were left out`}>
          Statements that contain formulas or variables, or that have a literal as subject, are valid N3 but not RDF, so they are not added to the data.
        </Notice>
      )}
      {details.warnings?.length > 0 && (
        <Notice tone="warning" title="EYE reported warnings">
          <ul className="plain-list">{details.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
        </Notice>
      )}
      {details.inferred_triples === 0 && (
        <Notice tone="info" title="Nothing new was inferred">
          Check that the rules use the same IRIs as your data. You can look them up under Knowledge graph, in Browse RDF.
        </Notice>
      )}

      {details.inferred_triples > 0 && (
        <div className="split even">
          <Breakdown title="Classes assigned" items={summary.classes} total={summary.class_count} empty="No rdf:type facts were inferred." />
          <Breakdown title="Properties added" items={summary.properties} total={summary.property_count} empty="Only rdf:type facts were inferred." />
        </div>
      )}

      {summary.sample.length > 0 && (
        <div className="results-panel">
          <div className="results-bar">
            <strong>Sample of inferred facts</strong>
            <span className="muted small">A few triples of every class and property</span>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Subject</th><th>Property</th><th>Value</th></tr></thead>
              <tbody>
                {summary.sample.map((row, index) => (
                  <tr key={index}>
                    <td><Term term={row.subject} /></td>
                    <td><span className="term-iri" title={row.predicate}>{shortIri(row.predicate)}</span></td>
                    <td><Term term={row.object} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="button-row">
        {inferredFile && <LinkButton icon="download" href={apiUrl(inferredFile.download_url)}>Inferred triples (Turtle)</LinkButton>}
        <Button variant="secondary" icon="database" onClick={() => navigate('graph')}>Download or publish reasoned RDF</Button>
        <Button variant="ghost" icon="shield" onClick={() => navigate('quality')}>Validate the result</Button>
      </div>
    </>
  )
}

function ExampleList({ examples, error, activeId, onUse }) {
  if (error) return <p className="field-error">The examples could not be loaded: {error}</p>
  if (!examples) return <div className="loading-row"><Spinner /> Loading examples</div>
  return (
    <div className="example-list">
      {examples.map((example) => {
        const active = example.id === activeId
        return (
          <div key={example.id} className={`example-item ${active ? 'active' : ''}`}>
            <div className="example-text">
              <strong>{example.title}</strong>
              <small>{example.summary}</small>
              <div className="chip-row">{example.features.map((feature) => <Badge key={feature}>{feature}</Badge>)}</div>
            </div>
            <Button variant={active ? 'secondary' : 'ghost'} icon={active ? 'refresh' : 'code'} onClick={() => onUse(example)}
              aria-label={`${active ? 'Reload' : 'Use'} the example ${example.title}`}>{active ? 'Reload' : 'Use'}</Button>
          </div>
        )
      })}
    </div>
  )
}

export default function ReasoningView({ run, config, busy, onRunStage, navigate, artifactsFor }) {
  const [rules, setRules] = useState(emptySource)
  const [exampleId, setExampleId] = useState(null)
  const [examples, setExamples] = useState({ items: null, error: '' })
  const reasoning = run?.stages?.reasoning
  const eye = config?.tools?.eye

  useEffect(() => {
    let active = true
    api.reasoningExamples()
      .then((value) => active && setExamples({ items: value.examples, error: '' }))
      .catch((reason) => active && setExamples({ items: null, error: reason.message }))
    return () => { active = false }
  }, [])

  if (!isDone(run, 'rml')) {
    return (
      <div className="view">
        <div className="view-header"><div><p className="eyebrow">Reasoning</p><h1>Infer new facts</h1></div></div>
        <Card><EmptyState icon="mapping" title="Generate RDF first"
          action={<button className="btn btn-primary" onClick={() => navigate(run ? 'mapping' : 'data')}>{run ? 'Go to Mapping' : 'Go to Data'}</button>}>
          The EYE reasoner applies N3 rules to the RDF produced by your mapping.
        </EmptyState></Card>
      </div>
    )
  }

  const example = examples.items?.find((item) => item.id === exampleId)
  const enriched = run.stages.rules?.status === 'success'
  const inputTriples = enriched ? run.stages.rules.details.total_triples : run.stages.rml.details.rdf_triples

  function loadExample(item) {
    const custom = rules.text.trim() && rules.text !== example?.rules
    if (custom && !window.confirm(`Replace the rules in the editor with the example “${item.title}”?`)) return
    setRules({ ...emptySource, text: item.rules })
    setExampleId(item.id)
  }

  function changeRules(value) {
    setRules(value)
    if (value.mode === 'file' || !value.text.trim()) setExampleId(null)
  }

  const body = {
    rules: rules.text,
    source_name: rules.mode === 'file' ? rules.fileName : null,
    example_id: example ? example.id : null,
  }

  return (
    <div className="view">
      <div className="view-header">
        <div><p className="eyebrow">Reasoning</p><h1>Infer new facts</h1>
          <p className="lede">Write N3 rules and let the EYE reasoner work out what follows from your data. The new facts are added to the RDF you validate, download, and publish.</p></div>
      </div>

      {eye && !eye.ready && <Notice tone="warning" title="The EYE reasoner is not available">{eye.detail}</Notice>}

      <div className="split">
        <Card title="N3 rules" icon="bulb" subtitle="Paste rules, upload an .n3 file, or start from an example.">
          <SourceInput id="n3-rules" label="Rules (N3)" value={rules} onChange={changeRules}
            accept=".n3,.ttl,.txt" fileLabel="N3 files" placeholder={PLACEHOLDER}
            hint={example ? `Example “${example.title}”: ${example.adds} Edit it as you like.` : undefined} />
          <div className="button-row">
            <Button icon="bulb" busy={busy === 'reasoning'} disabled={!rules.text.trim() || Boolean(busy) || eye?.ready === false}
              onClick={() => onRunStage('reasoning', body)}>Run reasoner</Button>
            {reasoning && <span className="muted small">Running again replaces the inferences and clears validation and publishing results.</span>}
          </div>
        </Card>

        <div className="stack">
          <Card title="Data being reasoned over" icon="database">
            <div className="fact-list">
              <div><span>Input</span><strong>{enriched ? 'Enriched RDF' : 'Mapped RDF'}</strong></div>
              <div><span>Triples</span><strong>{formatNumber(inputTriples)}</strong></div>
              <div><span>Reasoner</span><strong>{eye?.ready ? eye.version.replace(/ \(.*\)$/, '') : 'Not available'}</strong></div>
              <div><span>Build</span><strong>{eye?.engine === 'native' ? 'Native' : eye?.engine === 'bundled' ? 'WebAssembly (bundled)' : '—'}</strong></div>
            </div>
            <p className="muted small">{enriched
              ? 'Your SHACL rule inferences are included in the input.'
              : 'If you also apply SHACL rules, run the reasoner afterwards: applying rules clears the inferences.'}</p>
          </Card>
          <Card title="Examples" icon="sparkle" subtitle="Written for the sample water data (SOSA observations).">
            <ExampleList examples={examples.items} error={examples.error} activeId={example?.id} onUse={loadExample} />
          </Card>
        </div>
      </div>

      {reasoning && (
        <Card title="Inferences" icon="bulb">
          <StageResult result={reasoning}>
            {reasoning.status === 'success' && <Inferences result={reasoning} artifacts={artifactsFor('reasoning')} navigate={navigate} />}
          </StageResult>
        </Card>
      )}
    </div>
  )
}
