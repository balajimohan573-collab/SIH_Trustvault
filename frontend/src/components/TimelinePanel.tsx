import { useCallback, useEffect, useMemo, useState } from 'react'
import { ShieldIcon } from './icons'
import { Badge, EmptyState, Notice, Panel, Spinner } from './ui'
import { securityApi, type SecurityEvent } from '../api'

const TYPE_META: Record<string, { label: string; tone: 'green' | 'amber' | 'red' | 'violet' }> = {
  LOGIN_SUCCESS: { label: 'Login successful', tone: 'green' },
  LOGIN_FAILED: { label: 'Login failed', tone: 'red' },
  REGISTRATION: { label: 'Account registered', tone: 'green' },
  DEVICE_TRUSTED: { label: 'Device trusted', tone: 'green' },
  DEVICE_REMOVED: { label: 'Device removed', tone: 'amber' },
  STEP_UP: { label: 'Step-up verification', tone: 'violet' },
  STEP_UP_SUCCESS: { label: 'Step-up passed', tone: 'green' },
  STEP_UP_FAILED: { label: 'Step-up failed', tone: 'red' },
  BLOCKED: { label: 'Request blocked', tone: 'red' },
  TRUST_ADJUSTED: { label: 'Trust adjusted', tone: 'amber' },
}

function metaFor(t: string) {
  return TYPE_META[t] ?? { label: t.replace(/_/g, ' '), tone: 'amber' as const }
}

export default function TimelinePanel() {
  const [events, setEvents] = useState<SecurityEvent[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      const data = await securityApi.events()
      setEvents([...data].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()))
    } catch (e: any) {
      setErr(e.message || 'Could not load security events.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const grouped = useMemo(() => {
    const days = new Map<string, SecurityEvent[]>()
    for (const ev of events) {
      const key = new Date(ev.created_at).toDateString()
      if (!days.has(key)) days.set(key, [])
      days.get(key)!.push(ev)
    }
    return [...days.entries()]
  }, [events])

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900">Security Activity</h2>
          <p className="text-xs text-slate-500">Live security events recorded by the Trust Engine — logins, devices, trust adjustments and blocks</p>
        </div>
        {!loading && (
          <button onClick={load} className="text-xs font-semibold text-brand-600 hover:text-brand-700">
            Refresh
          </button>
        )}
      </div>

      {err && <Notice tone="red">{err}</Notice>}

      <Panel icon={<ShieldIcon className="h-5 w-5" />} title="Activity Log">
        {loading && events.length === 0 ? (
          <div className="flex items-center gap-2 py-16 justify-center">
            <Spinner className="h-5 w-5 text-brand-600" />
            <span className="text-xs font-semibold text-slate-500">Loading security events…</span>
          </div>
        ) : events.length === 0 ? (
          <EmptyState icon={<ShieldIcon className="h-5 w-5" />} title="No security events" hint="Events appear here as the engine records logins, device changes and blocks." />
        ) : (
          <div className="space-y-6">
            {grouped.map(([day, evs]) => (
              <div key={day}>
                <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 mb-2">{day}</p>
                <ol className="relative space-y-5 border-l border-slate-200 pl-6">
                  {evs.map((ev) => {
                    const meta = metaFor(ev.event_type)
                    return (
                      <li key={ev.id} className="relative">
                        <span className={`absolute -left-[31px] top-1.5 h-3.5 w-3.5 rounded-full ring-4 ring-white ${
                          meta.tone === 'red' ? 'bg-rose-500' : meta.tone === 'amber' ? 'bg-amber-500' : meta.tone === 'violet' ? 'bg-violet-500' : 'bg-emerald-500'
                        }`} />
                        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <h4 className="text-sm font-bold text-slate-900">{meta.label}</h4>
                              <Badge tone={meta.tone} dot className="text-[10px]">
                                {ev.decision ?? ev.event_type}
                              </Badge>
                            </div>
                            <span className="text-[11px] font-mono text-slate-400">
                              {new Date(ev.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            {ev.trust_score !== null && <>Trust score <b className="text-slate-700">{ev.trust_score}/100</b> · </>}
                            user <span className="font-mono">{ev.user_id?.slice(0, 10)}…</span>
                          </p>
                          {Object.keys(ev.risk_signals ?? {}).length > 0 && (
                            <p className="mt-2 rounded-lg bg-slate-50 border border-slate-100 p-2 font-mono text-[10px] text-slate-500">
                              {JSON.stringify(ev.risk_signals)}
                            </p>
                          )}
                        </div>
                      </li>
                    )
                  })}
                </ol>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}