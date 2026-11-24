// Same-origin by default: the backend serves the built UI, and the Vite dev
// server proxies /api. Set VITE_PIPELINE_API_URL only for a separately hosted API.
export const API_BASE = import.meta.env.VITE_PIPELINE_API_URL || ''

export const apiUrl = (path) => `${API_BASE}${path}`

async function request(path, options = {}) {
  const response = await fetch(apiUrl(path), options)
  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}.`
    const text = await response.text()
    try {
      const payload = JSON.parse(text)
      const detail = payload.detail
      if (typeof detail === 'string') message = detail
      else if (Array.isArray(detail)) message = detail.map((item) => item.msg).join(' ')
    } catch {
      if (text) message = text
    }
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  if (response.status === 204) return null
  return response.json()
}

const postJson = (path, body) => request(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body ?? {}),
})

export const api = {
  config: () => request('/api/config'),
  getRun: (runId) => request(`/api/runs/${runId}`),
  upload: (file) => {
    const body = new FormData()
    body.append('file', file)
    return request('/api/runs', { method: 'POST', body })
  },
  deleteRun: (runId) => request(`/api/runs/${runId}`, { method: 'DELETE' }),
  runStage: (runId, stage, body) => postJson(`/api/runs/${runId}/stages/${stage}`, body),
  reasoningExamples: () => request('/api/reasoning/examples'),
  rdfPreview: (runId, offset) => request(`/api/runs/${runId}/rdf-preview?offset=${offset}&limit=10`),
  rdfDownloadUrl: (runId, format) => apiUrl(`/api/runs/${runId}/rdf?format=${format}`),
  storeGraphs: () => request('/api/store/graphs'),
  operations: () => request('/api/store/operations'),
  runOperation: (operationId, parameters) => postJson(`/api/store/operations/${operationId}`, { parameters }),
  query: (query) => postJson('/api/store/query', { query }),
  runAgent: (body) => postJson('/api/orchestration/run', body),
  dropAgentOutputs: (environmentId, agentId) => request(
    `/api/orchestration/environments/${environmentId}/outputs${agentId ? `?agent_id=${agentId}` : ''}`,
    { method: 'DELETE' },
  ),
}
