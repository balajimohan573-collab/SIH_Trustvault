// TrustVault typed API client. All data flows from the backend — nothing is fabricated.
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

export type CurrentUser = {
  id: string
  email: string
  full_name: string | null
  did: string | null
  role: 'holder' | 'issuer' | 'verifier' | 'admin'
  status: string
}

let currentUser: CurrentUser | null = null

export function setAuth(t: string | null, user?: CurrentUser) {
  token = t
  currentUser = user ?? null
  if (t) localStorage.setItem('trustvault_token', t)
  else localStorage.removeItem('trustvault_token')
}

export function getToken() {
  return token
}

export function getCurrentUser(): CurrentUser | null {
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
  patch: <T>(path: string, body?: any) => request<T>('PATCH', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
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
export type TokenResponse = {
  access_token: string
  token_type: string
  user: CurrentUser
}

export type TrustedDevice = {
  id: string
  label: string
  browser: string | null
  os: string | null
  first_seen: string
  last_seen: string
  status: string
}

export const authApi = {
  register: (email: string, password: string, full_name?: string) =>
    api.post<TokenResponse>('/auth/register', { email, password, full_name }),
  login: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { email, password }),
  logout: () => api.post<{ ok: boolean }>('/auth/logout'),
  me: () => api.get<CurrentUser>('/auth/me'),
  changePassword: (old_password: string, new_password: string) =>
    api.post<{ ok: boolean }>('/auth/change-password', { old_password, new_password }),
  resetRequest: (email: string) =>
    api.post<{ ok: boolean; reset_token: string | null }>('/auth/password-reset/request', { email }),
  resetComplete: (token: string, new_password: string) =>
    api.post<{ ok: boolean }>('/auth/password-reset/complete', { token, new_password }),
  devices: () => api.get<TrustedDevice[]>('/auth/devices'),
  registerDevice: (label: string) =>
    api.post<{ id: string; label: string; status: string }>('/auth/devices', { label }),
  removeDevice: (id: string) => api.del<{ id: string; status: string }>(`/auth/devices/${id}`),
  // Passkey (WebAuthn) registration + login.
  registerStart: (email: string, role = 'holder') =>
    api.post<{ options: any }>('/auth/register/start', { email, role }),
  registerComplete: (email: string, credential: any, label = 'default') =>
    api.post<TokenResponse>('/auth/register/complete', { email, credential, label }),
  loginStart: (email: string) => api.post<{ options: any }>('/auth/login/start', { email }),
  loginComplete: (email: string, credential: any, label = 'default') =>
    api.post<TokenResponse>('/auth/login/complete', { email, credential, label }),
}

// ---- Users (admin browsing) ----
export const usersApi = {
  list: () => api.get<Array<{ id: string; email: string; role: string; status: string }>>('/auth/users'),
}

// ---- Organizations ----
export type Organization = {
  id: string
  name: string
  official_domain: string
  org_identifier: string | null
  verification_status: string
  verified_at: string | null
  created_at: string
}

export const orgApi = {
  list: () => api.get<Organization[]>('/organizations'),
  me: () => api.get<Organization | null>('/organizations/me'),
  apply: (name: string, official_domain: string, org_identifier?: string, evidence_uri?: string) =>
    api.post<Organization>('/organizations', {
      name,
      official_domain,
      org_identifier: org_identifier || null,
      evidence_uri: evidence_uri || null,
    }),
  decide: (org_id: string, approve: boolean, note?: string) =>
    api.post<Organization>(`/organizations/${org_id}/decide`, { approve, note: note || null }),
}

// ---- Credentials ----
export type CredentialClaim = {
  key: string
  value: string
  claim_type: string
  public: boolean
}

export type CredentialFile = {
  id: string
  original_filename: string
  sha256: string
  byte_size: number
  content_type: string
  detected_type: string
  is_primary: boolean
}

export type Credential = {
  id: string
  type: string
  title: string | null
  issuer_name: string | null
  issuer_org_id: string
  issuer_user_id: string
  holder_id: string
  status: string
  issue_date: string | null
  expiry_date: string | null
  external_id: string | null
  claims_hash: string
  hash: string | null
  anchor_tx_hash: string | null
  issued_at: string
  revoked_at: string | null
  suspended_at: string | null
  claims: CredentialClaim[]
  files: CredentialFile[]
}

export type QrGenerate = { qr_token: string; qr_url: string; expires_at: string }

export const credentialsApi = {
  list: () => api.get<Credential[]>('/credentials'),
  get: (id: string) => api.get<Credential>(`/credentials/${id}`),
  issue: (body: {
    holder_email?: string
    type: string
    title?: string
    external_id?: string
    issue_date?: string
    expiry_date?: string
    claims?: Array<{ key: string; value: string; claim_type?: string; public?: boolean }>
    document?: Record<string, any>
  }) => api.post<Credential>('/credentials', body),
  verify: (id: string) => api.get<{ id: string; valid: boolean; status: string; hash_match: boolean; purpose: string | null }>(`/credentials/${id}/verify`),
  generateQr: (credential_id: string, purpose?: string, expires_minutes = 5) =>
    api.post<QrGenerate>('/credentials/qr/generate', { credential_id, purpose, expires_minutes }),
  qrVerify: (qr_token: string) =>
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
  suspend: (id: string, reason?: string) => api.post<Credential>(`/credentials/${id}/suspend`, { reason: reason || null }),
  resume: (id: string) => api.post<Credential>(`/credentials/${id}/resume`),
  revoke: (id: string, reason?: string) => api.post<Credential>(`/credentials/${id}/revoke`, { reason: reason || null }),
}

// ---- Public verification ----
export const verifyApi = {
  byToken: (token: string) =>
    api.get<{
      valid: boolean
      result: string
      status: string
      credential_id: string | null
      holder_did: string | null
      holder_name: string | null
      type: string | null
      issuer_org: string | null
      issued_at: string | null
      expiry_date: string | null
      public_claims: Record<string, string>
      checks: Record<string, boolean>
      reason: string | null
      purpose: string | null
    }>(`/verify/${encodeURIComponent(token)}`),
  qrUrl: (token: string) => `${BASE}/verify/${encodeURIComponent(token)}/qr`,
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

// ---- Access (asset-based) ----
export type AccessRequest = {
  id: string
  asset_id: string
  requester_id: string
  purpose: string
  status: string
  created_at: string
  context_provided: Record<string, any> | null
}

export type Grant = {
  id: string
  asset_id: string
  purpose: string
  granted_at: string
  expires_at: string
}

export const assetAccessApi = {
  incoming: () => api.get<AccessRequest[]>('/access'),
  request: (asset_id: string, purpose: string, context?: Record<string, any>) =>
    api.post<AccessRequest>('/access/request', { asset_id, purpose, context: context ?? null }),
  approve: (request_id: string, duration_minutes = 30) =>
    api.post<Grant>(`/access/${request_id}/approve`, { decision: 'approve', duration_minutes }),
  deny: (request_id: string, duration_minutes = 30) =>
    api.post<{ status: string }>(`/access/${request_id}/deny`, { decision: 'deny', duration_minutes }),
  grant: (asset_id: string, purpose: string, duration_minutes = 60) =>
    api.post<Grant>('/access/grant', { asset_id, purpose, duration_minutes }),
  revokeGrant: (grant_id: string) =>
    api.post<{ id: string; status: string }>(`/access/grants/${grant_id}/revoke`),
}

// ---- Credential access (purpose-bound) ----
export type CredentialAccessRequest = {
  id: string
  credential_id: string
  requester_id: string
  purpose: string
  requested_claims: string[]
  status: string
  expires_at: string
  created_at: string
  decided_at: string | null
}

export type CredentialAccessGrant = {
  id: string
  credential_id: string
  requester_id: string
  purpose: string
  allowed_claims: string[]
  status: string
  granted_at: string
  expires_at: string
  revoked_at: string | null
}

export const credentialAccessApi = {
  request: (credential_id: string, purpose: string, requested_claims: string[], expires_minutes = 60) =>
    api.post<CredentialAccessRequest>('/access/credential/request', {
      credential_id,
      purpose,
      requested_claims,
      expires_minutes,
    }),
  requests: (scope: 'incoming' | 'outgoing' | 'pending' = 'incoming') =>
    api.get<CredentialAccessRequest[]>(`/access/credential/requests?scope=${scope}`),
  grants: () => api.get<CredentialAccessGrant[]>('/access/credential/grants'),
  grantsAll: () => api.get<CredentialAccessGrant[]>('/access/credential/grants/all'),
  approve: (request_id: string, duration_minutes = 60) =>
    api.post<CredentialAccessGrant>(`/access/credential/${request_id}/approve`, { duration_minutes }),
  deny: (request_id: string, duration_minutes = 60) =>
    api.post<{ status: string }>(`/access/credential/${request_id}/deny`, { duration_minutes }),
  revokeGrant: (grant_id: string) =>
    api.post<{ id: string; status: string }>(`/access/credential/grants/${grant_id}/revoke`),
  content: (credential_id: string) =>
    api.get<{
      credential_id: string
      holder_did: string
      type: string
      issued_at: string | null
      purpose: string
      claims: Record<string, string>
      granted_until: string
    }>(`/access/credential/content/${credential_id}`),
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

export const trustApi = {
  get: (user_id: string) => api.get<TrustState>(`/trust/${user_id}`),
}

// ---- Timeline / audit ----
export type SecurityEvent = {
  id: string
  user_id: string | null
  event_type: string
  risk_signals: Record<string, any>
  trust_score: number | null
  decision: Decision | null
  created_at: string
}

export const securityApi = {
  events: () => api.get<SecurityEvent[]>('/security/events'),
}

export const auditApi = {
  forAsset: (asset_id: string) =>
    api.get<
      Array<{
        event_id: string
        event_type: string
        trust_score: number | null
        decision: string | null
        risk_signals: Record<string, any>
        created_at: string
        anchor: Record<string, any> | null
      }>
    >(`/audit/${asset_id}`),
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

// ---- Notifications ----
export type Notification = {
  id: string
  type: string
  title: string
  body: string
  link: string | null
  read: boolean
  created_at: string
}

export const notificationsApi = {
  list: () => api.get<Notification[]>('/notifications'),
  unreadCount: () => api.get<{ count: number }>('/notifications/unread-count'),
  markRead: (id: string) => api.patch<{ id: string; read: boolean }>(`/notifications/${id}/read`),
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