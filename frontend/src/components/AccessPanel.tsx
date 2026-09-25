import { useCallback, useEffect, useState } from 'react'
import {
  assetAccessApi,
  credentialAccessApi,
  credentialsApi,
  type Credential,
  type CredentialAccessGrant,
  type CredentialAccessRequest,
} from '../api'
import { BadgeCheckIcon, KeyIcon, ShieldIcon } from './icons'
import { Badge, BtnGhost, BtnPrimary, EmptyState, Field, Input, Notice, Panel, Select } from './ui'

export default function AccessPanel() {
  const [msg, setMsg] = useState<{ tone: 'green' | 'red' | 'amber'; text: string } | null>(null)
  const [creds, setCreds] = useState<Credential[]>([])

  // Requester form
  const [credId, setCredId] = useState('')
  const [purpose, setPurpose] = useState('Employment verification')
  const [claimKeys, setClaimKeys] = useState('')
  const [expiry, setExpiry] = useState('60')

  // Lists
  const [incoming, setIncoming] = useState<CredentialAccessRequest[]>([])
  const [outgoing, setOutgoing] = useState<CredentialAccessRequest[]>([])
  const [grants, setGrants] = useState<CredentialAccessGrant[]>([])
  const [holderGrants, setHolderGrants] = useState<CredentialAccessGrant[]>([])
  const [assetIncoming, setAssetIncoming] = useState<any[]>([])

  const notify = (text: string, tone: 'green' | 'red' | 'amber' = 'green') => setMsg({ tone, text })
  const credMap = new Map(creds.map((c) => [c.id, c.title ?? c.type]))

  const load = useCallback(async () => {
    try {
      setIncoming(await credentialAccessApi.requests('incoming'))
    } catch { /* role-gated view */ }
    try {
      setOutgoing(await credentialAccessApi.requests('outgoing'))
    } catch { /* no-op */ }
    try {
      setGrants(await credentialAccessApi.grants())
    } catch { /* no-op */ }
    try {
      setHolderGrants(await credentialAccessApi.grantsAll())
    } catch { /* no-op */ }
    try {
      setAssetIncoming(await assetAccessApi.incoming())
    } catch { /* no-op */ }
  }, [])

  useEffect(() => {
    load()
    credentialsApi.list().then(setCreds).catch(() => {})
  }, [load])

  async function submitRequest() {
    setMsg(null)
    if (!credId.trim() || !purpose.trim()) {
      notify('Credential ID and purpose are required.', 'red')
      return
    }
    const claims = claimKeys
      .split(',')
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean)
    try {
      await credentialAccessApi.request(credId.trim(), purpose.trim(), claims, Number(expiry) || 60)
      notify('Purpose-bound access request created. The holder must approve it before you can read the credential.')
      setCredId('')
      setClaimKeys('')
      await load()
    } catch (e: any) {
      notify(e.message || 'Request failed.', 'red')
    }
  }

  async function decide(id: string, approve: boolean) {
    setMsg(null)
    try {
      if (approve) await credentialAccessApi.approve(id, 60)
      else await credentialAccessApi.deny(id)
      notify(approve ? 'Access approved — the requester can now read the allowed claims.' : 'Access request denied.')
      await load()
    } catch (e: any) {
      notify(e.message || 'Decision failed.', 'red')
    }
  }

  async function revokeGrant(id: string) {
    setMsg(null)
    try {
      await credentialAccessApi.revokeGrant(id)
      notify('Grant revoked. The requester can no longer read this credential.')
      await load()
    } catch (e: any) {
      notify(e.message || 'Revoke failed.', 'red')
    }
  }

  async function assetDecide(id: string, approve: boolean) {
    setMsg(null)
    try {
      if (approve) await assetAccessApi.approve(id, 60)
      else await assetAccessApi.deny(id)
      notify(approve ? 'Asset access approved.' : 'Asset access denied.')
      await load()
    } catch (e: any) {
      notify(e.message || 'Decision failed.', 'red')
    }
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-slate-900">Access Requests & Shared Permissions</h2>
        <p className="text-xs text-slate-500">
          Request purpose-bound credential access, approve requests on your credentials, and revoke grants.
        </p>
      </div>

      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Request access (requester side) */}
        <Panel
          title="Request access"
          subtitle="Ask a holder for time-limited access to a credential"
          icon={<KeyIcon className="h-5 w-5" />}
          help="The holder will approve or deny. Approved requests become grants that expire automatically."
        >
          <div className="space-y-3.5">
            <Field label="Credential ID" hint="the holder shares the credential's ID with you">
              <Input value={credId} onChange={(e) => setCredId(e.target.value)} placeholder="credential-uuid" className="font-mono text-xs" />
            </Field>
            <Field label="Purpose">
              <Input value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="Why do you need it?" />
            </Field>
            <Field label="Requested claims" hint="comma separated, e.g. full_name, degree">
              <Input value={claimKeys} onChange={(e) => setClaimKeys(e.target.value)} placeholder="full_name, degree" className="font-mono text-xs" />
            </Field>
            <Field label="Expiry">
              <Select value={expiry} onChange={(e) => setExpiry(e.target.value)}>
                <option value="15">15 minutes</option>
                <option value="60">1 hour</option>
                <option value="480">8 hours</option>
                <option value="1440">24 hours</option>
                <option value="4320">3 days</option>
              </Select>
            </Field>
            <BtnPrimary className="w-full" onClick={submitRequest}>
              Create Access Request
            </BtnPrimary>
          </div>
        </Panel>

        {/* Incoming requests (holder side) */}
        <Panel
          title="Incoming requests"
          subtitle="Access requests awaiting your decision"
          icon={<ShieldIcon className="h-5 w-5" />}
        >
          {incoming.length === 0 && assetIncoming.length === 0 ? (
            <EmptyState icon={<ShieldIcon className="h-5 w-5" />} title="Nothing pending" hint="Requests from verifiers on your credentials and documents appear here." />
          ) : (
            <div className="space-y-3">
              {incoming.map((r) => (
                <div key={r.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-xs">
                      <p className="font-bold text-slate-900">{credMap.get(r.credential_id) ?? r.credential_id.slice(0, 12) + '…'}</p>
                      <p className="mt-0.5 text-slate-500">
                        wants: <b className="text-slate-700">{r.purpose}</b> · claims: {r.requested_claims.length ? r.requested_claims.join(', ') : 'all'}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <BtnGhost className="!px-3 !py-1.5 text-xs text-rose-600 border border-rose-200" onClick={() => decide(r.id, false)}>
                        Deny
                      </BtnGhost>
                      <BtnPrimary className="!px-3 !py-1.5 text-xs" onClick={() => decide(r.id, true)}>
                        Allow
                      </BtnPrimary>
                    </div>
                  </div>
                </div>
              ))}
              {assetIncoming.map((r) => (
                <div key={r.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-xs">
                      <p className="font-bold text-slate-900">Document {String(r.asset_id).slice(0, 12)}…</p>
                      <p className="mt-0.5 text-slate-500">{r.purpose}</p>
                    </div>
                    <div className="flex gap-2">
                      <BtnGhost className="!px-3 !py-1.5 text-xs text-rose-600 border border-rose-200" onClick={() => assetDecide(r.id, false)}>
                        Deny
                      </BtnGhost>
                      <BtnPrimary className="!px-3 !py-1.5 text-xs" onClick={() => assetDecide(r.id, true)}>
                        Allow
                      </BtnPrimary>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      {/* My requests */}
      <Panel title="My access requests" subtitle="Requests you created as a requester" icon={<KeyIcon className="h-5 w-5" />}>
        {outgoing.length === 0 ? (
          <EmptyState icon={<KeyIcon className="h-5 w-5" />} title="No outgoing requests" hint="Create one above using a credential ID shared by a holder." />
        ) : (
          <div className="space-y-3">
            {outgoing.map((r) => (
              <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50/50 p-4">
                <div className="text-xs">
                  <p className="font-bold text-slate-900">{credMap.get(r.credential_id) ?? r.credential_id.slice(0, 12) + '…'}</p>
                  <p className="mt-0.5 text-slate-500">{r.purpose} · expires {new Date(r.expires_at).toLocaleString()}</p>
                </div>
                <Badge tone={r.status === 'pending' ? 'amber' : r.status === 'approved' ? 'green' : 'red'} dot>
                  {r.status}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {/* Grant registry */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Panel title="Grants I received" subtitle="Credential access granted to you by holders" icon={<BadgeCheckIcon className="h-5 w-5" />}>
          {grants.length === 0 ? (
            <EmptyState icon={<BadgeCheckIcon className="h-5 w-5" />} title="No grants yet" hint="Approved requests become grants you can read." />
          ) : (
            <div className="space-y-3">
              {grants.map((g) => (
                <div key={g.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50/50 p-4">
                  <div className="text-xs">
                    <p className="font-bold text-slate-900">{credMap.get(g.credential_id) ?? g.credential_id.slice(0, 12) + '…'}</p>
                    <p className="mt-0.5 text-slate-500">
                      {g.purpose} · claims: {g.allowed_claims.length ? g.allowed_claims.join(', ') : 'all'} · expires{' '}
                      {new Date(g.expires_at).toLocaleString()}
                    </p>
                  </div>
                  <Badge tone={g.status === 'active' ? 'green' : 'red'} dot>{g.status}</Badge>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Access on my credentials" subtitle="Who currently holds access to what you hold" icon={<BadgeCheckIcon className="h-5 w-5" />}>
          {holderGrants.length === 0 ? (
            <EmptyState icon={<BadgeCheckIcon className="h-5 w-5" />} title="No active access" hint="Approved grants on your credentials appear here and can be revoked anytime." />
          ) : (
            <div className="space-y-3">
              {holderGrants.map((g) => (
                <div key={g.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50/50 p-4">
                  <div className="text-xs">
                    <p className="font-bold text-slate-900">{credMap.get(g.credential_id) ?? g.credential_id.slice(0, 12) + '…'}</p>
                    <p className="mt-0.5 text-slate-500">
                      {g.purpose} · requester {g.requester_id.slice(0, 10)}… · expires {new Date(g.expires_at).toLocaleString()}
                    </p>
                  </div>
                  <BtnGhost className="!px-3 !py-1.5 text-xs text-rose-600 border border-rose-200" onClick={() => revokeGrant(g.id)}>
                    Revoke
                  </BtnGhost>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}