import { useState } from 'react'
import { emptySource, formatNumber } from '../format.js'
import SourceInput from '../components/SourceInput.jsx'
import { Badge, Button, Card, CopyButton, EmptyState, Kpi, StageResult } from '../components/ui.jsx'

const PLACEHOLDER = `@prefix rr:  <http://www.w3.org/ns/r2rml#> .
@prefix rml: <http://semweb.mmlab.be/ns/rml#> .
@prefix ql:  <http://semweb.mmlab.be/ns/ql#> .

<#Mapping> a rr:TriplesMap ;
  rml:logicalSource [ rml:source "your-file.csv" ; rml:referenceFormulation ql:CSV ] ;
  rr:subjectMap [ rr:template "https://example.org/item/{id}" ] .`

export default function MappingView({ run, busy, onRunStage, navigate }) {
  const [mapping, setMapping] = useState(emptySource)
  const source = run?.source
  const result = run?.stages?.rml

  if (!source?.preview) {
    return (
      <div className="view">
        <div className="view-header"><div><p className="eyebrow">Mapping</p><h1>Map data to RDF</h1></div></div>
        <Card><EmptyState icon="table" title="Upload a dataset first"
          action={<button className="btn btn-primary" onClick={() => navigate('data')}>Go to Data</button>}>
          The mapping runs against the columns of your uploaded file.
        </EmptyState></Card>
      </div>
    )
  }

  const run_ = () => onRunStage('rml', {
    mapping: mapping.text,
    source_name: mapping.mode === 'file' ? mapping.fileName : null,
  })

  return (
    <div className="view">
      <div className="view-header">
        <div><p className="eyebrow">Mapping</p><h1>Map data to RDF</h1>
          <p className="lede">Provide an RML mapping that turns the rows of <strong>{source.stored_filename}</strong> into RDF.</p></div>
      </div>

      <div className="split">
        <Card title="RML mapping" icon="mapping" subtitle="Paste the mapping or upload a Turtle file.">
          <SourceInput id="rml-source" label="Mapping (Turtle)" value={mapping} onChange={setMapping}
            accept=".ttl,.rml,.txt" placeholder={PLACEHOLDER} />
          <div className="button-row">
            <Button icon="play" busy={busy === 'rml'} disabled={!mapping.text.trim()} onClick={run_}>Generate RDF</Button>
            {result && <span className="muted small">Running again replaces the RDF and clears quality results and publishing.</span>}
          </div>
          <StageResult result={result}>
            {result?.status === 'success' && (
              <>
                <div className="kpi-grid compact">
                  <Kpi label="RDF triples" value={formatNumber(result.details.rdf_triples)} tone="success" />
                  <Kpi label="Mapping rules (triples)" value={formatNumber(result.details.mapping_triples)} />
                  <Kpi label="Mapping from" value={result.details.mapping_source?.startsWith('uploaded') ? 'File' : 'Editor'}
                    hint={result.details.mapping_source} />
                </div>
                <div className="button-row">
                  <Button variant="secondary" icon="database" onClick={() => navigate('graph')}>Browse, download, or publish</Button>
                  <Button variant="ghost" icon="shield" onClick={() => navigate('quality')}>Check data quality</Button>
                </div>
              </>
            )}
          </StageResult>
        </Card>

        <div className="stack">
          <Card title="Logical source" icon="file" subtitle="Reference this file name in rml:source.">
            <div className="source-name"><code>{source.mapping_source_filename}</code><CopyButton text={source.mapping_source_filename} /></div>
            <p className="muted small">Use the name only, not a local path. Your data is copied into an isolated workspace.</p>
          </Card>
          <Card title="Available columns" icon="table" subtitle="Use these exact names in rr:template and rml:reference.">
            <div className="chip-row">
              {source.preview.columns.map((column) => <Badge key={column}>{column}</Badge>)}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
