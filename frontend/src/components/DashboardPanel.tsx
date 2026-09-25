import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { dashboardApi, duressApi, recoveryApi, offlineApi, type DashboardSummary } from '../api'
import { Badge, EmptyState, Notice, Panel, BtnGhost, BtnDanger, Spinner, Tip, cn } from './ui'
import {
  DashboardIcon,
  ShieldIcon,
  ServerIcon,
  ShieldAlertIcon,
  RefreshIcon,
  AlertIcon,
  CheckIcon,
} from './icons'

function Stat({ label, value, tone = 'brand' }: { label: string; value: ReactNode; tone?: 'brand' | 'green' | 'amber' | 'red' | 'violet' | 'slate' }) {
  const tones = {
    brand: 'border-brand-100 bg-brand-50 text-brand-700',
    green: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
    red: 'border-rose-200 bg-rose-50 text-rose-700',
    violet: 'border-violet-200 bg-violet-50 text-violet-700',
    slate: 'border-slate-200 bg-slate-50 text-slate-700',
  }
  return (
    <div className={cn('rounded-xl border px-4 py-3', tones[tone])}>
      <p className="text-[10px] font-semibold uppercase tracking-widest opacity-70">{label}</p>
      <p className="mt-1 text-lg font-bold">{value}</p>
    </div>
  )
}

function Dict({ data }: { data: Record<string, any> }) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {Object.entries(data ?? {}).map(([k, v]) => (
        <div key={k} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{k.replace(/_/g, ' ')}</p>
          <p className="mt-0.5 truncate text-sm font-semibold text-slate-800">{String(v)}</p>
        </div>
      ))}
    </div>
  )
}

export default function DashboardPanel() {
  const [sum, setSum] = useState<DashboardSummary | null>(null)
  const [technical, setTechnical] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [duress, setDuress] = useState<{ active: boolean; id: string | null } | null>(null)
  const [dMsg, setDMsg] = useState<string | null>(null)
  const [recovery, setRecovery] = useState<any[]>([])
  const [busy, setBusy] = useState(false)

  async function load() {
    try {
      setSum((await dashboardApi.summary(technical)) as DashboardSummary)
      const d = await duressApi.status()
      setDuress(d.active ? d : { active: false, id: null })
    } catch (e: any) {
      setErr(e.message)
    }
  }
  useEffect(() => {
    load()
  }, [technical])

  async function loadRecovery() {
    try {
      setRecovery(await recoveryApi.list())
    } catch {
      /* role-restricted view */
    }
  }
  useEffect(() => {
    loadRecovery()
  }, [])

  async function toggleDuress() {
    setBusy(true)
    setDMsg(null)
    try {
      if (duress?.active) await duressApi.deactivate()
      else await duressApi.activate()
      setDMsg(duress?.active ? 'Duress cleared.' : 'Duress active — sensitive access is frozen. A silent alert was recorded.')
    } catch (e: any) {
      setDMsg(e.detail ?? e.message)
    } finally {
      setBusy(false)
      setDuress(null)
      await load()
    }
  }

  async function recoveryRequest() {
    setBusy(true)
    setDMsg(null)
    try {
      await recoveryApi.request('replacement device')
      setDMsg('Recovery request queued for approval — recorded as a security event.')
      await loadRecovery()
    } catch (e: any) {
      setDMsg(e.detail ?? e.message)
    } finally {
      setBusy(false)
    }
  }

  async function offlineSync() {
    setBusy(true)
    setDMsg(null)
    try {
      const r = await offlineApi.sync()
      setDMsg(`Offline sync: ${r.synced} event(s) anchored to the audit trail.`)
    } catch (e: any) {
      setDMsg(e.detail ?? e.message)
    } finally {
      setBusy(false)
    }
  }

  const dAlerts = (sum?.recent_activity ?? []).filter((e) => e.decision && e.decision !== 'ALLOW')

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Role" value={sum?.user_role ?? '—'} tone={sum?.user_role === 'admin' ? 'red' : sum?.user_role === 'issuer' ? 'brand' : sum?.user_role === 'verifier' ? 'violet' : 'green'} />
        <Stat label="Identity" value={sum?.user_role === 'admin' ? (sum.identities?.total_users ?? 0) : `${Object.values(sum?.identities ?? {}).join('') ? 'Verified' : '—'}`} />
        <Stat
          label="Credentials"
          tone={sum?.credentials?.held_revoked ?? sum?.credentials?.issued_revoked ? 'red' : 'brand'}
          value={sum?.user_role === 'admin' ? sum?.credentials?.issued_total ?? 0 : sum?.credentials?.held_total ?? 0}
        />
        <Stat label="Assets / NFT" value={sum?.assets?.owned_total ?? 0} tone={sum?.assets?.nft_minted ? 'brand' : 'slate'} />
      </div>

      {err && <Notice tone="red">{err}</Notice>}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Panel
          title="Identity & credentials"
          subtitle={sum?.trust?.model_version ? `Rules engine: ${sum.trust.model_version}` : 'Rules engine: rules-v2'}
          icon={<ShieldIcon className="h-5 w-5" />}
          className="lg:col-span-1"
        >
          {sum?.user_role === 'admin' ? (
            <Dict data={sum.identities} />
          ) : (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-600">
              {Object.entries(sum?.identities ?? {}).map(([k, v]) => (
                <p key={k} className="truncate py-0.5">
                  {k}: {String(v)}
                </p>
              ))}
            </div>
          )}
          <div className="mt-3 space-y-1">
            {sum?.trust?.current_score !== null && sum?.trust?.current_score !== undefined && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Latest trust score</span>
                <Badge tone={sum.trust.current_score >= 70 ? 'green' : sum.trust.current_score >= 40 ? 'amber' : 'red'} dot>
                  {sum.trust.current_score}
                </Badge>
              </div>
            )}
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500">QR verification</span>
              <Badge tone="brand">5-min tokens</Badge>
            </div>
          </div>
        </Panel>

        <Panel
          title="Pending access requests"
          subtitle="Approvals live in the Access tab"
          icon={<AlertIcon className="h-5 w-5" />}
          className="lg:col-span-1"
        >
          {sum?.pending_requests?.length === 0 ? (
            <EmptyState icon={<AlertIcon className="h-5 w-5" />} title="Nothing pending" hint="Open the Access tab to approve purpose-and-time-bound grants." />
          ) : (
            <ul className="space-y-2">
              {(sum?.pending_requests ?? []).map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                  <span className="text-slate-700">
                    <b>{r.purpose}</b> · asset {String(r.asset_id).slice(0, 8)}…
                  </span>
                  <Badge tone="amber">pending</Badge>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title="Security posture"
          subtitle="Non-ALLOW decisions in the last activity window"
          icon={<ShieldAlertIcon className="h-5 w-5" />}
          className="lg:col-span-1"
        >
          {dAlerts.length === 0 ? (
            <EmptyState icon={<CheckIcon className="h-5 w-5" />} title="No active alerts" hint="STEP_UP / RESTRICTED / DENY events will surface here." />
          ) : (
            <ul className="space-y-2">
              {dAlerts.slice(0, 6).map((e) => (
                <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                  <span className="font-mono text-[10px] text-slate-600">{e.event_type}</span>
                  <Badge tone={e.decision === 'STEP_UP' ? 'amber' : 'red'} dot>
                    {e.decision}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel
        title="Recent activity"
        subtitle="Most recent security events — technical view toggle for admins/auditors"
        icon={<DashboardIcon className="h-5 w-5" />}
        actions={
          sum?.user_role === 'admin' || sum?.user_role === 'auditor' ? (
            <div className="flex items-center gap-2">
              <Tip label="Show deployment flags, table counts and chain settings — the Technical view.">
                <BtnGhost className="!px-3 !py-1.5 text-xs" onClick={() => setTechnical(!technical)}>
                  <ServerIcon className="h-3.5 w-3.5" />
                  {technical ? 'Hide technical' : 'Technical'}
                </BtnGhost>
              </Tip>
            </div>
          ) : null
        }
      >
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div>
            {(sum?.recent_activity ?? []).length === 0 ? (
              <EmptyState title="No activity yet" hint="Events land here as the Trust Engine evaluates requests." />
            ) : (
              <ul className="space-y-2">
                {(sum?.recent_activity ?? []).slice(0, 8).map((e) => (
                  <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                    <span className="font-mono text-[10px] text-slate-600">{e.event_type}</span>
                    {e.decision && <Badge tone={e.decision === 'ALLOW' ? 'green' : 'slate'}>{e.decision}</Badge>}
                    <span className="text-[10px] text-slate-400">{new Date(e.created_at).toLocaleTimeString()}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {technical && sum?.technical ? (
            <div className="space-y-4">
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-400">Deployment flags</p>
                <Dict data={sum.technical.flags ?? {}} />
              </div>
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-400">Counts</p>
                <Dict data={sum.technical.counts ?? {}} />
              </div>
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-400">Chain</p>
                <pre className="overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-[10px] leading-relaxed text-slate-600">
                  {JSON.stringify(sum.technical.chain ?? {}, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Quick actions</p>
              <div className="flex flex-wrap gap-2">
                <Tip label="Anchor pending offline decisions recorded during connectivity gaps.">
                  <BtnGhost className="!px-3 !py-2 text-xs" onClick={offlineSync} disabled={busy}>
                    <RefreshIcon className="h-3.5 w-3.5" />
                    Sync offline
                  </BtnGhost>
                </Tip>
                <Tip label="Device lost? File a replacement request — a first-class security event.">
                  <BtnGhost className="!px-3 !py-2 text-xs" onClick={recoveryRequest} disabled={busy}>
                    Report device loss
                  </BtnGhost>
                </Tip>
                <Tip label="Covert freeze: while active, all your sensitive access is DENIED and the event is recorded. Disabled if the deployment opts out.">
                  {duress?.active ? (
                    <BtnDanger className="!px-3 !py-2 text-xs" onClick={toggleDuress} disabled={busy}>
                      {busy && <Spinner />}
                      Clear duress
                    </BtnDanger>
                  ) : (
                    <BtnGhost className="!px-3 !py-2 text-xs" onClick={toggleDuress} disabled={busy}>
                      Activate duress
                    </BtnGhost>
                  )}
                </Tip>
              </div>
              {dMsg && <Notice tone={dMsg.toLowerCase().includes('duress') ? 'red' : 'green'}>{dMsg}</Notice>}
              {recovery.length > 0 && (
                <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                  <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">My recovery requests</p>
                  {recovery.map((r) => (
                    <p key={r.id} className="mt-1 flex items-center gap-2 text-xs text-slate-600">
                      <span>{new Date(r.requested_at).toLocaleDateString()}</span>
                      <Badge tone={r.status === 'approved' ? 'green' : r.status === 'denied' ? 'red' : 'amber'} dot>
                        {r.status}
                      </Badge>
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </Panel>
    </div>
  )
}