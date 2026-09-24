import { useEffect, useState } from 'react'
import { api, type AccessRequest, type Asset } from '../api'
import { Badge, EmptyState, Field, Notice, Panel, BtnGhost, BtnPrimary, BtnDanger, Input, Select } from './ui'
import { ClockIcon, KeyIcon, UserIcon } from './icons'

export default function AccessPanel() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [requests, setRequests] = useState<AccessRequest[]>([])
  const [reqAsset, setReqAsset] = useState('')
  const [reqPurpose, setReqPurpose] = useState('employment')
  const [msg, setMsg] = useState<{ tone: 'green' | 'red' | 'amber' | 'slate'; text: string } | null>(null)

  async function refresh() {
    setAssets(await api.get<Asset[]>('/assets'))
    setRequests(await api.get<AccessRequest[]>('/access'))
  }

  useEffect(() => {
    refresh().catch(() => {})
  }, [])

  async function requestAccess() {
    setMsg(null)
    try {
      await api.post('/access/request', { asset_id: reqAsset, purpose: reqPurpose })
      setMsg({ tone: 'green', text: `Access request created for ${reqPurpose} — waiting for owner approval.` })
      await refresh()
    } catch (e: any) {
      setMsg({
        tone: 'red',
        text: `Request rejected: ${typeof e.detail === 'object' ? JSON.stringify(e.detail) : e.message}`,
      })
    }
  }

  async function decide(id: string, d: 'approve' | 'deny', minutes = 30) {
    setMsg(null)
    const r = await api
      .post(`/access/${id}/${d}`, { decision: d, duration_minutes: d === 'approve' ? minutes : 30 })
      .catch((e: any) => {
        setMsg({ tone: 'red', text: `${d} failed: ${e.message}` })
        return null
      })
    if (r) {
      setMsg(
        d === 'approve'
          ? { tone: 'green', text: `Grant created — purpose- and time-bound (${minutes}m).` }
          : { tone: 'amber', text: 'Request denied.' },
      )
    }
    await refresh()
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <Panel
        title="Request access"
        subtitle="Requester asks; owner grants a scoped, expiring grant"
        icon={<KeyIcon className="h-5 w-5" />}
      >
        <div className="space-y-3.5">
          <Field label="Asset" hint="the document you need">
            <Select value={reqAsset} onChange={(e) => setReqAsset(e.target.value)}>
              <option value="">Select asset…</option>
              {assets.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.id.slice(0, 8)}…)
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Purpose" hint="why you need access">
            <Input value={reqPurpose} onChange={(e) => setReqPurpose(e.target.value)} placeholder="purpose" />
          </Field>
          <BtnPrimary className="w-full" onClick={requestAccess} disabled={!reqAsset}>
            Submit access request
          </BtnPrimary>
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        </div>
      </Panel>

      <Panel
        title="Incoming requests"
        subtitle="Owner approves with an expiry window, or denies"
        icon={<UserIcon className="h-5 w-5" />}
      >
        {requests.length === 0 ? (
          <EmptyState
            icon={<UserIcon className="h-5 w-5" />}
            title="No incoming requests"
            hint="Requests land here for the asset owner to approve or deny with a scoped, time-bound grant."
          />
        ) : (
          <div className="space-y-3">
            {requests.map((r) => (
              <div key={r.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md border border-brand-200 bg-brand-50 px-1.5 py-0.5 font-mono text-[11px] text-brand-700">
                    {r.asset_id.slice(0, 8)}…
                  </span>
                  <span className="text-sm font-medium text-slate-800">{r.purpose}</span>
                  <span className="ml-auto">
                    <Badge tone={r.status === 'approved' ? 'green' : r.status === 'denied' ? 'red' : 'slate'} dot>
                      {r.status}
                    </Badge>
                  </span>
                </div>
                <p className="mt-1.5 font-mono text-[10px] text-slate-500">
                  requester {r.requester_id.slice(0, 10)}… · {new Date(r.created_at).toLocaleString()}
                </p>
                {r.status === 'pending' && (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5">
                      <ClockIcon className="h-3.5 w-3.5 text-slate-500" />
                      <input
                        type="number"
                        defaultValue={30}
                        min={1}
                        max={1440}
                        id={`dur-${r.id}`}
                        className="w-14 bg-transparent text-xs text-slate-800 outline-none"
                        title="Grant duration in minutes"
                      />
                      <span className="text-[10px] text-slate-500">min</span>
                    </div>
                    <BtnGhost
                      className="!px-3 !py-1.5 text-xs !text-emerald-600 hover:!border-emerald-400 hover:!text-emerald-700"
                      onClick={() => decide(r.id, 'approve', Number((document.getElementById(`dur-${r.id}`) as HTMLInputElement)?.value ?? 30))}
                    >
                      Approve
                    </BtnGhost>
                    <BtnDanger className="!px-3 !py-1.5 text-xs" onClick={() => decide(r.id, 'deny')}>
                      Deny
                    </BtnDanger>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}