import { useEffect, useState } from 'react'
import { api, type AccessRequest, type Asset } from '../api'
import { Badge, EmptyState, Field, Notice, Panel, BtnPrimary, Input, Select, SpeakerButton, cn } from './ui'
import { ClockIcon, KeyIcon, UserIcon } from './icons'
import { useLang, tr, speak } from '../i18n'

const BIG = {
  allow: {
    icon: '✓',
    active: 'bg-emerald-500 hover:bg-emerald-600 shadow-emerald-500/30',
    hit: 'allow_hit',
  },
  ask_again: {
    icon: '⟳',
    active: 'bg-amber-500 hover:bg-amber-600 shadow-amber-500/30',
    hit: 'ask_again_hit',
  },
  block: {
    icon: '✕',
    active: 'bg-rose-600 hover:bg-rose-700 shadow-rose-600/30',
    hit: 'block_hit',
  },
} as const

export default function AccessPanel() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [requests, setRequests] = useState<AccessRequest[]>([])
  const [reqAsset, setReqAsset] = useState('')
  const [reqPurpose, setReqPurpose] = useState('employment')
  const [msg, setMsg] = useState<{ tone: 'green' | 'red' | 'amber' | 'slate'; text: string } | null>(null)
  const lang = useLang()

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

  async function bigTap(r: AccessRequest, kind: keyof typeof BIG) {
    const minutes = Number((document.getElementById(`dur-${r.id}`) as HTMLInputElement)?.value ?? 30)
    if (kind === 'allow') await decide(r.id, 'approve', minutes)
    else await decide(r.id, 'deny', minutes)
    speak(tr(lang, BIG[kind].hit), lang)
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
                      {r.status === 'approved' ? tr(lang, 'status_approved') : r.status === 'denied' ? tr(lang, 'status_denied') : tr(lang, 'status_pending')}
                    </Badge>
                  </span>
                </div>
                <p className="mt-1.5 font-mono text-[10px] text-slate-500">
                  requester {r.requester_id.slice(0, 10)}… · {new Date(r.created_at).toLocaleString()}
                </p>
                {r.status === 'pending' && (
                  <div className="mt-4">
                    <div className="flex flex-wrap items-center gap-2 text-[11px]">
                      <span className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5">
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
                      </span>
                      <span className="text-slate-500">{tr(lang, 'request_status')}</span>
                      <SpeakerButton
                        text={`${tr(lang, 'request_status')}. ${tr(lang, 'allow')}, ${tr(lang, 'ask_again')}, ${tr(lang, 'block')}?`}
                        tone="slate"
                      />
                    </div>

                    <div className="mt-3 grid grid-cols-3 gap-2">
                      {(Object.keys(BIG) as (keyof typeof BIG)[]).map((k) => (
                        <button
                          key={k}
                          disabled={false}
                          onClick={() => bigTap(r, k)}
                          className={cn(
                            'flex flex-col items-center justify-center gap-1 rounded-2xl px-2 py-4 text-sm font-bold text-white shadow-lg transition active:scale-95',
                            BIG[k].active,
                          )}
                        >
                          <span className="text-xl leading-none">{BIG[k].icon}</span>
                          {tr(lang, k === 'allow' ? 'allow' : k === 'ask_again' ? 'ask_again' : 'block')}
                        </button>
                      ))}
                    </div>
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