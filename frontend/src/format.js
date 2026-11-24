/** Initial value for a SourceInput (pasted or uploaded semantic contract). */
export const emptySource = { mode: 'paste', text: '', fileName: '', fileSize: 0 }

export const completedStatuses = new Set(['success', 'nonconformant'])

export const isDone = (run, stage) => completedStatuses.has(run?.stages?.[stage]?.status)

/** The RDF that validation, downloads, and publishing use: reasoned, else enriched, else mapped. */
export function currentRdf(run) {
  const stages = run?.stages || {}
  const mapped = stages.rml?.details?.rdf_triples
  if (stages.reasoning?.status === 'success') {
    return { kind: 'reasoned', label: 'Reasoned RDF', triples: stages.reasoning.details.total_triples, mapped }
  }
  if (stages.rules?.status === 'success') {
    return { kind: 'enriched', label: 'Enriched RDF', triples: stages.rules.details.total_triples, mapped }
  }
  return { kind: 'mapped', label: 'Mapped RDF', triples: mapped, mapped }
}

/** True for the temporary graphs that Agent orchestration keeps for agent outputs. */
export const isAgentOutput = (uri, config) => Boolean(config?.orchestration_graph_base) && String(uri).startsWith(config.orchestration_graph_base)

export function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Number(value).toLocaleString()
}

export function compactNumber(value) {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

export function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  const trim = (value) => value.toFixed(1).replace(/\.0$/, '')
  if (bytes < 1024 * 1024) return `${trim(bytes / 1024)} KB`
  return `${trim(bytes / 1024 / 1024)} MB`
}

export function timeAgo(isoString) {
  if (!isoString) return ''
  const seconds = Math.max(0, (Date.now() - new Date(isoString).getTime()) / 1000)
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return new Date(isoString).toLocaleDateString()
}

/** Last readable segment of an IRI, for compact display. A numeric segment keeps its parent (sensor/123). */
export function shortIri(value) {
  if (!value) return ''
  const text = String(value)
  if (!/^[a-z][a-z0-9+.-]*:/i.test(text)) return text
  const trimmed = text.replace(/[/#]+$/, '')
  let cut = Math.max(trimmed.lastIndexOf('#'), trimmed.lastIndexOf('/'))
  if (cut > 0 && /^\d+$/.test(trimmed.slice(cut + 1))) {
    const parent = Math.max(trimmed.lastIndexOf('#', cut - 1), trimmed.lastIndexOf('/', cut - 1))
    if (parent > trimmed.indexOf('//') + 1) cut = parent
  }
  const tail = cut >= 0 ? trimmed.slice(cut + 1) : trimmed
  try {
    return decodeURIComponent(tail) || text
  } catch {
    return tail || text
  }
}

export function datasetStem(run) {
  const name = run?.source?.stored_filename || 'dataset'
  return name.replace(/\.[^.]+$/, '') || 'dataset'
}

function csvCell(value) {
  const text = value === undefined || value === null ? '' : String(value)
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export function bindingsToCsv(variables, rows) {
  const lines = [variables.map(csvCell).join(',')]
  for (const row of rows) lines.push(variables.map((variable) => csvCell(row[variable]?.value)).join(','))
  return lines.join('\r\n')
}

export function downloadText(filename, text, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}
