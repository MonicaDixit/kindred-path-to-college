const BASE = import.meta.env.VITE_API_BASE || '/api'

async function req(path, opts) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch (_) {}
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  resources: () => req('/resources'),
  colleges: () => req('/colleges'),
  college: (id) => req(`/colleges/${id}`),
  agents: () => req('/agents'),
  session: (id) => req(`/session/${id}`),
  chat: (session_id, message, profile) =>
    req('/chat', {
      method: 'POST',
      body: JSON.stringify({ session_id, message, profile }),
    }),
}
