import { useEffect, useState } from 'react'
import { api, type SecurityEvent } from '../api'
import { Badge, EmptyState, Panel, decisionTone, cn } from './ui'
import { ActivityIcon, CheckIcon, XIcon, AlertIcon, InfoIcon } from './icons'
import { useLang, tr } from '../i18n'

export default function TimelinePanel() {
  const [events, setEvents] = useState<SecurityEvent[]>([])
  const lang = useLang()

  useEffect(() => {
    const t = setInterval(async () => {
      try {
        setEvents(await api.get<SecurityEvent[]>('/security/events'))
      } catch {
        /* ignore */
      }
    }, 3000)
    return () => clearInterval(t)
  }, [])

  return (
    <Panel
      title={tr(lang, 'nav_timeline')}
      subtitle="What happened to your account, as it happens"
      icon={<ActivityIcon className="h-5 w-5" />}
      actions={
        <Badge tone="green" dot className="animate-pulse">
          {tr(lang, 'live')}
        </Badge>
      }
    >
      {events.length === 0 ? (
        <EmptyState
          icon={<ActivityIcon className="h-5 w-5" />}
          title="Nothing to show yet"
          hint="Events land here as things happen — approvals, blocks, and anything unusual. Run a demo to see it fill up."
        />
      ) : (
        <ol className="relative space-y-4 border-l border-slate-200 pl-6">
          {events.map((e) => {
            const tone = decisionTone(e.decision ?? '')
            const Icon = e.decision === 'ALLOW' ? CheckIcon : e.decision === 'RESTRICTED' ? InfoIcon : e.decision === 'STEP_UP' ? AlertIcon : XIcon
            const nodeColor = e.decision === 'ALLOW' ? 'bg-emerald-500' : e.decision === 'STEP_UP' ? 'bg-amber-500' : e.decision === 'RESTRICTED' ? 'bg-violet-500' : 'bg-rose-500'
            const decLabel = e.decision ? tr(lang, `dec_${e.decision}`) : null
            return (
              <li key={e.id} className="relative">
                <span
                  className={cn(
                    'absolute -left-[37px] top-1.5 grid h-5 w-5 -translate-x-0 place-items-center rounded-full ring-4 ring-white',
                    nodeColor,
                  )}
                >
                  <Icon className="h-3 w-3 text-white" />
                </span>
                <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm transition hover:border-slate-300">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md border border-brand-200 bg-brand-50 px-1.5 py-0.5 font-mono text-[11px] text-brand-700">
                      {e.event_type}
                    </span>
                    {decLabel && <Badge tone={tone}>{decLabel}</Badge>}
                    {e.trust_score !== null && (
                      <span className={cn('font-mono text-[11px]', e.trust_score >= 70 ? 'text-slate-500' : e.trust_score >= 40 ? 'text-amber-600' : 'text-rose-600')}>
                        security {e.trust_score}
                      </span>
                    )}
                    <span className="ml-auto font-mono text-[10px] text-slate-400">
                      {new Date(e.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  {Object.keys(e.risk_signals ?? {}).length > 0 && (
                    <details className="mt-2 group">
                      <summary className="cursor-pointer text-[11px] text-slate-500 transition hover:text-slate-700">
                        Technical details
                      </summary>
                      <pre className="mt-2 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-2.5 font-mono text-[10px] leading-relaxed text-slate-500">
                        {JSON.stringify(e.risk_signals, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </Panel>
  )
}