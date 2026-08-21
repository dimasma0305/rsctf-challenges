const MAX_ERROR_BYTES = 2048

export function requiredEnvironment(name) {
  const value = process.env[name]?.trim()
  if (!value) throw new Error(`${name} is required`)
  return value
}

export function positiveIntegerEnvironment(name) {
  const raw = requiredEnvironment(name)
  const value = Number(raw)
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new Error(`${name} must be a positive integer`)
  }
  return value
}

export function optionalNonNegativeIntegerEnvironment(name) {
  const raw = process.env[name]?.trim()
  if (!raw) return undefined
  const value = Number(raw)
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new Error(`${name} must be a non-negative integer`)
  }
  return value
}

export function serviceUrl(name) {
  const value = new URL(requiredEnvironment(name))
  if (!['http:', 'https:'].includes(value.protocol)) {
    throw new Error(`${name} must use http or https`)
  }
  if (value.username || value.password || value.search || value.hash) {
    throw new Error(`${name} must not contain credentials, a query, or a fragment`)
  }
  value.pathname = `${value.pathname.replace(/\/+$/, '')}/`
  return value
}

export async function requestJson(base, path, token, { method = 'GET', body } = {}) {
  const url = new URL(path.replace(/^\/+/, ''), base)
  const headers = {
    Accept: 'application/json',
    Authorization: `Bearer ${token}`,
  }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    redirect: 'error',
    signal: AbortSignal.timeout(15_000),
  })
  const text = await response.text()
  if (!response.ok) {
    throw new Error(`${method} ${url.pathname} returned HTTP ${response.status}: ${text.slice(0, MAX_ERROR_BYTES)}`)
  }
  try {
    return JSON.parse(text)
  } catch {
    throw new Error(`${method} ${url.pathname} did not return JSON`)
  }
}

export async function readJsonStdin(limit = 16 * 1024) {
  const chunks = []
  let total = 0
  for await (const chunk of process.stdin) {
    total += chunk.length
    if (total > limit) throw new Error(`stdin JSON exceeds ${limit} bytes`)
    chunks.push(chunk)
  }
  if (total === 0) throw new Error('stdin JSON is required')
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'))
  } catch {
    throw new Error('stdin is not valid JSON')
  }
}
