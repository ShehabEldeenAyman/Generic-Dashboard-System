// Tests for the display helpers in src/format.js (run with: npm test).
import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import {
  bindingsToCsv, currentRdf, datasetStem, emptySource, formatBytes, formatNumber, isAgentOutput, isDone, shortIri, timeAgo,
} from '../src/format.js'

describe('numbers and sizes', () => {
  test('numbers use the local format and missing values show a dash', () => {
    assert.equal(formatNumber(1234567), (1234567).toLocaleString())
    assert.equal(formatNumber(null), '—')
    assert.equal(formatNumber('not a number'), '—')
  })

  test('sizes are shown in B, KB, or MB without a trailing .0', () => {
    assert.equal(formatBytes(0), '0 B')
    assert.equal(formatBytes(512), '512 B')
    assert.equal(formatBytes(1536), '1.5 KB')
    assert.equal(formatBytes(1024 * 1024), '1 MB')
    assert.equal(formatBytes(50 * 1024 * 1024), '50 MB')
    assert.equal(formatBytes(undefined), '—')
  })
})

describe('IRIs', () => {
  test('short IRIs keep the parent of a numeric segment', () => {
    assert.equal(shortIri('http://example.com/observations/289435042/1756684800'), '289435042/1756684800')
    assert.equal(shortIri('http://example.com/waterinfo/289435042'), 'waterinfo/289435042')
    assert.equal(shortIri('http://example.com/123'), '123')
    assert.equal(shortIri('http://www.w3.org/1999/02/22-rdf-syntax-ns#type'), 'type')
    assert.equal(shortIri('https://example.org/graphs/people%202026'), 'people 2026')
    assert.equal(shortIri('plain text'), 'plain text')
    assert.equal(shortIri(''), '')
  })

  test('agent output graphs are recognised from the configured base', () => {
    const config = { orchestration_graph_base: 'https://example.org/graphs/orchestration/' }
    assert.equal(isAgentOutput('https://example.org/graphs/orchestration/env/agent', config), true)
    assert.equal(isAgentOutput('https://example.org/graphs/waterinfo', config), false)
    assert.equal(isAgentOutput('https://example.org/graphs/orchestration/env/agent', null), false)
  })
})

describe('datasets', () => {
  const run = (stages) => ({ stages: { rml: { status: 'success', details: { rdf_triples: 100 } }, ...stages } })

  test('the current RDF is reasoned, else enriched, else mapped', () => {
    assert.deepEqual(currentRdf(run({})), { kind: 'mapped', label: 'Mapped RDF', triples: 100, mapped: 100 })
    const enriched = run({ rules: { status: 'success', details: { total_triples: 120 } } })
    assert.equal(currentRdf(enriched).kind, 'enriched')
    const reasoned = run({
      rules: { status: 'success', details: { total_triples: 120 } },
      reasoning: { status: 'success', details: { total_triples: 150 } },
    })
    assert.deepEqual(currentRdf(reasoned), { kind: 'reasoned', label: 'Reasoned RDF', triples: 150, mapped: 100 })
    const failed = run({ reasoning: { status: 'error', details: {} } })
    assert.equal(currentRdf(failed).kind, 'mapped')
  })

  test('stage status and dataset names', () => {
    assert.equal(isDone({ stages: { shacl: { status: 'nonconformant' } } }, 'shacl'), true)
    assert.equal(isDone({ stages: { shacl: { status: 'error' } } }, 'shacl'), false)
    assert.equal(isDone(null, 'rml'), false)
    assert.equal(datasetStem({ source: { stored_filename: 'sales.2026.csv' } }), 'sales.2026')
    assert.equal(datasetStem(null), 'dataset')
    assert.deepEqual(emptySource, { mode: 'paste', text: '', fileName: '', fileSize: 0 })
  })
})

describe('results and times', () => {
  test('CSV export quotes commas, quotes, and line breaks', () => {
    const rows = [{ name: { value: 'Smith, "Jo"' }, note: { value: 'line 1\nline 2' } }, { name: { value: 'plain' } }]
    assert.equal(bindingsToCsv(['name', 'note'], rows), 'name,note\r\n"Smith, ""Jo""","line 1\nline 2"\r\nplain,')
  })

  test('times are shown relative to now', () => {
    const ago = (seconds) => new Date(Date.now() - seconds * 1000).toISOString()
    assert.equal(timeAgo(ago(5)), 'just now')
    assert.equal(timeAgo(ago(5 * 60)), '5 min ago')
    assert.equal(timeAgo(ago(3 * 3600)), '3 h ago')
    assert.equal(timeAgo(ago(3 * 86400)), new Date(ago(3 * 86400)).toLocaleDateString())
    assert.equal(timeAgo(''), '')
  })
})
