/** Initial value for a SourceInput (pasted or uploaded semantic contract). */
export const emptySource = { mode: 'paste', text: '', fileName: '', fileSize: 0 }

export const completedStatuses = new Set(['success', 'nonconformant'])

export const isDone = (run, stage) => completedStatuses.has(run?.stages?.[stage]?.status)

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

/** Last readable segment of an IRI, for compact display. */
export function shortIri(value) {
  if (!value) return ''
  const text = String(value)
  if (!/^[a-z][a-z0-9+.-]*:/i.test(text)) return text
  const trimmed = text.replace(/[/#]+$/, '')
  const cut = Math.max(trimmed.lastIndexOf('#'), trimmed.lastIndexOf('/'))
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
