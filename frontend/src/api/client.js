const BASE = ''
let authToken = localStorage.getItem('eco_token')

export function setToken(t) { authToken = t }
export function getToken() { return authToken }

export async function request(method, path, body = null, params = {}) {
  const url = new URL(path, window.location.origin)
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))

  const headers = { 'Content-Type': 'application/json' }
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`

  const opts = { method, headers }
  if (body && method !== 'GET') opts.body = JSON.stringify(body)

  const r = await fetch(url, opts)
  const data = await r.json()
  if (!r.ok) throw { status: r.status, ...data }
  return data
}

export default {
  get: (path, params) => request('GET', path, null, params),
  post: (path, body, params) => request('POST', path, body, params),
  delete: (path) => request('DELETE', path),
}
