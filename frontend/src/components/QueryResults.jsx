import { bindingsToCsv, downloadText, formatNumber, shortIri } from '../format.js'
import { Badge, Button, Icon } from './ui.jsx'

function Term({ term }) {
  if (!term) return <em className="muted">—</em>
  if (term.type === 'uri') {
    return <span className="term-iri" title={term.value}>{shortIri(term.value)}</span>
  }
  return (
    <span title={term.datatype ? `${term.value} (${shortIri(term.datatype)})` : term.value}>
      {term.value}
      {term['xml:lang'] && <small className="term-lang">@{term['xml:lang']}</small>}
    </span>
  )
}

/** Renders a SPARQL result returned by the API: select table, ask boolean, or graph text. */
export default function QueryResults({ result, filename = 'query-results' }) {
  if (!result) return null

  if (result.type === 'ask') {
    return (
      <div className={`ask-result ${result.boolean ? 'yes' : 'no'}`}>
        <Icon name={result.boolean ? 'check' : 'x'} size={22} />
        <div><strong>{result.boolean ? 'Yes' : 'No'}</strong><span>ASK query result</span></div>
      </div>
    )
  }

  if (result.type === 'graph') {
    return (
      <div className="query-output">
        <div className="results-bar">
          <span><Badge tone="info">{result.content_type}</Badge>{result.truncated && <Badge tone="warning">Preview truncated</Badge>}</span>
          <Button variant="secondary" icon="download" onClick={() => downloadText(`${filename}.ttl`, result.text, result.content_type)}>Download</Button>
        </div>
        <pre className="code-block">{result.text}</pre>
      </div>
    )
  }

  const variables = result.variables || []
  const rows = result.rows || []
  return (
    <div className="query-output">
      <div className="results-bar">
        <span>
          <strong>{formatNumber(result.row_count)} row{result.row_count === 1 ? '' : 's'}</strong>
          {result.truncated && <Badge tone="warning">Capped by server</Badge>}
        </span>
        <Button variant="secondary" icon="download" disabled={!rows.length}
          onClick={() => downloadText(`${filename}.csv`, bindingsToCsv(variables, rows), 'text/csv')}>Export CSV</Button>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr>{variables.map((variable) => <th key={variable}>{variable}</th>)}</tr></thead>
          <tbody>
            {rows.length ? rows.map((row, index) => (
              <tr key={index}>{variables.map((variable) => <td key={variable}><Term term={row[variable]} /></td>)}</tr>
            )) : (
              <tr><td colSpan={Math.max(variables.length, 1)} className="table-empty">No matching results.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
