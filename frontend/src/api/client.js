const BASE = import.meta.env.VITE_API_BASE_URL || ''

export async function request(method, path, body = null, params = {}) {
  const url = new URL(path, BASE || window.location.origin)
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))

  const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' }

  const opts = { method, headers, credentials: 'include' }
  if (body && method !== 'GET') opts.body = JSON.stringify(body)

  const r = await fetch(url, opts)
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw { status: r.status, ...data }
  return data
}

export default {
  get: (path, params) => request('GET', path, null, params),
  post: (path, body, params) => request('POST', path, body, params),
  delete: (path) => request('DELETE', path),
}
