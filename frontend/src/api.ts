// TrustVault typed API client.
const BASE = '/api'

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

let token: string | null = localStorage.getItem('trustvault_token')
let currentUser: any = null

export function setAuth(t: string | null, user?: any) {
  token = t
  currentUser = user ?? null
  if (t) localStorage.setItem('trustvault_token', t)
  else localStorage.removeItem('trustvault_token')
}

export function getToken() {
  return token
}

export function getCurrentUser() {
  return currentUser
}

async function request<T>(method: string, path: string, body?: any, isForm?: boolean): Promise<T> {
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (body && !isForm) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: isForm ? (body as FormData) : body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail: unknown = res.statusText
    try {
      const j = await res.json()
      detail = j.detail ?? j
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: any) => request<T>('POST', path, body),
  upload: <T>(path: string, form: FormData) => request<T>('POST', path, form, true),
  download: async (path: string) => {
    const res = await fetch(`${BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) {
      let detail: unknown = res.statusText
      try {
        const j = await res.json()
        detail = j.detail ?? j
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail)
    }
    return res.blob()
  },
}

// ---- Auth ----
export const authApi = {
  devLogin: (email: string) =>
    api.post<{ access_token: string; user: any }>('/auth/login/dev', { email }),
  me: () => api.get<any>('/auth/me'),
}

// ---- Credentials ----
export type Credential = {
  id: string
  type: string
  hash: string
  status: string
  issuer_id: string
  holder_id: string
  issued_at: string
  revoked_at: string | null
}

// ---- Assets ----
export type Decision = 'ALLOW' | 'STEP_UP' | 'RESTRICTED' | 'DENY'

export type Asset = {
  id: string
  owner_id: string
  name: string
  encrypted_uri: string
  file_hash: string
  cid: string | null
  content_type: string
  asset_class: string
  nft_token_id: string | null
  chain_tx_hash: string | null
  transferred_at: string | null
  created_at: string
}

export type AssetPolicy = {
  id: string
  asset_id: string
  requester_role: string
  purpose: string
  min_trust: number
  expires_at: string | null
  location_scope: string | null
  location_strict: boolean
  time_start: string | null
  time_end: string | null
  time_zone: string | null
  context_required: Record<string, any> | null
}

export type AssetOwnership = {
  asset_id: string
  owner_id: string
  nft_token_id: string | null
  chain_tx_hash: string | null
  transferred_at: string | null
  history: Array<{
    id: string
    from_user_id: string
    to_user_id: string
    reason: string | null
    created_at: string
  }>
}

export type AccessDecisionReason = { code: string; human: string }
export type AccessDecisionOut = {
  decision: Decision
  human: string
  next_action: string | null
  scope: string | null
  severity: string
  trust_score: number | null
  reasons: string[]
  reasons_human: AccessDecisionReason[]
  model_version: string | null
}

// ---- Access ----
export type AccessRequest = {
  id: string
  asset_id: string
  requester_id: string
  purpose: string
  status: string
  created_at: string
}

// ---- Trust ----
export type TrustState = {
  user_id: string
  trust_score: number
  decision: 'ALLOW' | 'STEP_UP' | 'RESTRICTED' | 'DENY'
  reasons: string[]
  model_version: string
  timestamp: string
  components: Record<string, number>
  ml_signal: number | null
}

// ---- Timeline ----
export type SecurityEvent = {
  id: string
  user_id: string | null
  event_type: string
  risk_signals: Record<string, any>
  trust_score: number | null
  decision: string | null
  created_at: string
}

// ---- QR verification (V2) ----
export const qrApi = {
  generate: (credential_id: string, purpose?: string, expires_minutes?: number) =>
    api.post<{ qr_token: string; qr_url: string; expires_at: string }>(
      '/credentials/qr/generate',
      { credential_id, purpose, expires_minutes },
    ),
  verify: (qr_token: string) =>
    api.post<{
      id: string
      valid: boolean
      status: string
      hash_match: boolean
      holder_did: string | null
      type: string | null
      issuer_id: string | null
      issued_at: string | null
      purpose: string | null
      expires_at: string | null
      selective_disclosure_ready: boolean
      explanation: string | null
    }>('/credentials/qr/verify', { qr_token }),
}

// ---- Dashboard (V2) ----
export type DashboardSummary = {
  user_role: string
  identities: Record<string, any>
  credentials: Record<string, any>
  assets: Record<string, any>
  pending_requests: Array<Record<string, any>>
  recent_activity: Array<Record<string, any>>
  security_alerts: Array<Record<string, any>>
  trust: { model_version: string; current_score: number | null } | null
  technical: Record<string, any> | null
}
export const dashboardApi = {
  summary: (technical = false) =>
    api.get<DashboardSummary>(`/dashboard/summary?technical=${technical}`),
}

// ---- Offline (V2) ----
export const offlineApi = {
  queue: (events: Array<Record<string, any>>) =>
    api.post<{ received: number; synced: number; deduped: number; failed: number }>(
      '/offline/queue',
      { events },
    ),
  sync: () =>
    api.post<{ received: number; synced: number; deduped: number; failed: number }>('/offline/sync'),
  events: () => api.get<Array<Record<string, any>>>('/offline/events'),
}

// ---- Recovery (V2) ----
export const recoveryApi = {
  request: (reason?: string) =>
    api.post<{ id: string; user_id: string; status: string; reason: string | null; requested_at: string }>(
      '/recovery/request',
      { reason },
    ),
  list: () => api.get<Array<{ id: string; user_id: string; status: string; reason: string | null; requested_at: string }>>('/recovery'),
  decide: (id: string, status: string) =>
    api.post<{ id: string; status: string }>(`/recovery/${id}/decide?status=${status}`),
}

// ---- Duress (V2) ----
export const duressApi = {
  status: () => api.get<{ active: boolean; id: string | null }>('/duress/status'),
  activate: () => api.post<{ id: string; active: boolean; expires_at: string; note: string }>('/duress/activate'),
  deactivate: () => api.post<{ id: string; active: boolean }>('/duress/deactivate'),
}