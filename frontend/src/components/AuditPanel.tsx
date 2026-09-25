import { useCallback, useEffect, useState } from 'react'
import { FileTextIcon, ShieldIcon } from './icons'
import { Badge, EmptyState, Notice, Panel, Spinner } from './ui'
import { dashboardApi, securityApi, type CurrentUser, type SecurityEvent } from '../api'

type Summary = {
  user_role?: string
  identities?: Record<string, any>
  credentials?: Record<string, any>
  assets?: Record<string, any>
  pending_requests?: any[]
  recent_activity?: any[]
  trust?: Record<string, any>
  technical?: { flags?: Record<string, any>; counts?: Record<string, number>; chain?: Record<string, any> }
}

const STATUS_TONE: Record<string, 'green' | 'amber' | 'red' | 'violet'> = {
  ALLOWED: 'green',
  VERIFIED: 'green',
  BLOCKED: 'red',
  DENIED: 'red',
  STEP_UP: 'amber',
  PENDING: 'amber',
}

export default function AuditPanel({ user }: { user: CurrentUser }) {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [events, setEvents] = useState<SecurityEvent[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const isAdmin = user.role === 'admin'

  const load = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      const [sum, evs] = await Promise.all([
        dashboardApi.summary(true),
        securityApi.events(),
      ])
      setSummary(sum as Summary)
      setEvents([...evs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()))
    } catch (e: any) {
      setErr(e.message || 'Could not load audit data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const counts = summary?.technical?.counts ?? {}
  const flags = summary?.technical?.flags ?? {}
  const chain = summary?.technical?.chain ?? {}
  const cred = summary?.credentials ?? {}
  const iden = summary?.identities ?? {}

  const kpis: { label: string; value: number | string; tone?: string }[] = []

  if (isAdmin) {
    kpis.push({ label: 'Total Users', value: iden.total_users ?? '—' })
    kpis.push({ label: 'Registered Devices', value: iden.registered_devices ?? '—' })
    kpis.push({ label: 'Credentials (all)', value: counts.credentials ?? '—' })
    kpis.push({ label: 'Documents', value: counts.assets ?? '—' })
    kpis.push({ label: 'Pending Requests', value: counts.pending_requests ?? '—' })
  } else {
    const totals = Object.keys(cred).length ? cred : undefined
    kpis.push({ label: 'Held Credentials', value: totals?.held_total ?? '—' })
    kpis.push({ label: 'Active', value: totals?.held_active ?? '—' })
    kpis.push({ label: 'Revoked', value: totals?.held_revoked ?? '—' })
    kpis.push({ label: 'Credentials across vault', value: counts.credentials ?? '—' })
    kpis.push({ label: 'Documents across vault', value: counts.assets ?? '—' })
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-slate-900">Security & Audit Overview</h2>
        <p className="text-xs text-slate-500">
          {isAdmin ? 'Platform-wide metrics, registries and live security events' : 'Your role-scoped counters and live security events'}
        </p>
      </div>

      {err && <Notice tone="red">{err}</Notice>}

      {loading && !summary ? (
        <div className="flex items-center justify-center gap-2 py-20">
          <Spinner className="h-5 w-5 text-brand-600" />
          <span className="text-xs font-semibold text-slate-500">Loading audit data…</span>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {kpis.map((k) => (
              <div key={k.label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-[11px] font-medium text-slate-500">{k.label}</p>
                <p className={`mt-1 text-2xl font-bold ${k.tone ?? 'text-slate-900'}`}>{k.value}</p>
              </div>
            ))}
          </div>

          {/* Technical flags */}
          <Panel title="Platform flags & registries" icon={<ShieldIcon className="h-5 w-5" />} subtitle="Read from live backend configuration">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-xs">
                <p className="text-slate-500">Chain anchoring</p>
                <p className={`mt-0.5 font-mono font-bold ${flags.chain_enabled ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {flags.chain_enabled ? 'enabled' : 'disabled'}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-xs">
                <p className="text-slate-500">Offline vault</p>
                <p className={`mt-0.5 font-mono font-bold ${flags.offline_enabled ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {flags.offline_enabled ? 'enabled' : 'disabled'}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-xs">
                <p className="text-slate-500">Duress mode</p>
                <p className={`mt-0.5 font-mono font-bold ${flags.duress_enabled ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {flags.duress_enabled ? 'enabled' : 'disabled'}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-xs">
                <p className="text-slate-500">QR expiry</p>
                <p className="mt-0.5 font-mono font-bold text-slate-700">{flags.qr_expiry_minutes ?? '—'} min</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-xs">
                <p className="text-slate-500">ML anomaly</p>
                <p className={`mt-0.5 font-mono font-bold ${flags.ml_anomaly ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {flags.ml_anomaly ? 'enabled' : 'disabled'}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-xs">
                <p className="text-slate-500">Audit registry</p>
                <p className="mt-0.5 font-mono font-bold text-slate-500 truncate">{chain.audit_registry ?? 'not configured'}</p>
              </div>
            </div>
          </Panel>

          {/* Recent Security Events Table */}
          <Panel title={isAdmin ? 'Recent security events (all users)' : 'My recent security events'} icon={<FileTextIcon className="h-5 w-5" />}>
            {events.length === 0 ? (
              <EmptyState icon={<FileTextIcon className="h-5 w-5" />} title="No events recorded" hint="Security events will appear here as activity happens." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-400 uppercase tracking-wider text-[10px]">
                      <th className="pb-3 font-semibold">User</th>
                      <th className="pb-3 font-semibold">Event</th>
                      <th className="pb-3 font-semibold">Trust</th>
                      <th className="pb-3 font-semibold">Time</th>
                      <th className="pb-3 font-semibold text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {events.slice(0, 15).map((ev) => {
                      const tone = STATUS_TONE[ev.decision ?? ''] ?? 'amber'
                      return (
                        <tr key={ev.id} className="hover:bg-slate-50/50">
                          <td className="py-3.5 font-mono font-bold text-slate-700">{ev.user_id?.slice(0, 10)}…</td>
                          <td className="py-3.5 text-slate-700">{ev.event_type.replace(/_/g, ' ')}</td>
                          <td className="py-3.5 font-mono text-slate-500">{ev.trust_score ?? '—'}</td>
                          <td className="py-3.5 font-mono text-slate-500">{new Date(ev.created_at).toLocaleString()}</td>
                          <td className="py-3.5 text-right">
                            <Badge tone={tone} dot>{ev.decision ?? ev.event_type}</Badge>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      )}
    </div>
  )
}