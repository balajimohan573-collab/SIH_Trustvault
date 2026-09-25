import { useCallback, useEffect, useState } from 'react'
import { ChevronDownIcon, RefreshCwIcon, ShieldIcon } from './icons'
import { Badge, BtnGhost, BtnPrimary, EmptyState, Notice, Panel, Spinner } from './ui'
import { trustApi, type CurrentUser, type TrustState } from '../api'
import StepUpAuthModal from './StepUpAuthModal'

const DECISION_TONE: Record<TrustState['decision'], 'green' | 'amber' | 'red' | 'violet'> = {
  ALLOW: 'green',
  STEP_UP: 'amber',
  RESTRICTED: 'violet',
  DENY: 'red',
}

const DECISION_LABEL: Record<TrustState['decision'], string> = {
  ALLOW: 'Access allowed',
  STEP_UP: 'Step-up verification',
  RESTRICTED: 'Limited access',
  DENY: 'Access blocked',
}

export default function TrustPanel({ user }: { user: CurrentUser }) {
  const [state, setState] = useState<TrustState | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [openWhy, setOpenWhy] = useState(true)
  const [openStepUp, setOpenStepUp] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      setState(await trustApi.get(user.id))
    } catch (e: any) {
      setErr(e.message || 'Could not load trust state.')
    } finally {
      setLoading(false)
    }
  }, [user.id])

  useEffect(() => {
    load()
  }, [load])

  const curr = state
  const R = 52
  const CIRC = 2 * Math.PI * R
  const color = curr ? (curr.decision === 'ALLOW' ? '#10b981' : curr.decision === 'STEP_UP' ? '#f59e0b' : curr.decision === 'RESTRICTED' ? '#8b5cf6' : '#f43f5e') : '#cbd5e1'

  if (loading && !curr) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="h-6 w-6 text-brand-600" />
        <span className="ml-2 text-xs font-semibold text-slate-500">Computing live trust state…</span>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Top Banner */}
      <div className="rounded-3xl border border-ink-700 bg-gradient-to-r from-slate-900 via-slate-800 to-brand-950 p-6 sm:p-8 text-white shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-brand-200 backdrop-blur-md">
              <ShieldIcon className="h-3.5 w-3.5" /> Trust Engine · live evaluation
            </span>
            <h1 className="mt-2 text-2xl font-bold tracking-tight">Your Live Security State</h1>
            <p className="mt-1 text-xs text-slate-300 max-w-lg leading-relaxed">
              The Trust Engine evaluates identity, device, behaviour, context and history on every request. This is your current
              standing — not a simulation.
            </p>
          </div>
          <BtnGhost
            onClick={load}
            className="!border-white/20 !bg-white/10 !text-white hover:!bg-white/20"
          >
            <RefreshCwIcon className="h-3.5 w-3.5" />
            Refresh
          </BtnGhost>
        </div>
      </div>

      {err && <Notice tone="red">{err}</Notice>}

      {!curr ? (
        <EmptyState
          icon={<ShieldIcon className="h-6 w-6" />}
          title="Trust state unavailable"
          hint="The engine could not produce a state for this account right now."
        />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Score Gauge Card */}
          <div className="rounded-3xl border border-ink-700 bg-white p-6 shadow-sm flex flex-col items-center justify-between text-center">
            <div className="w-full flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Security Check</span>
              <Badge tone={DECISION_TONE[curr.decision]} dot className="px-3 py-1 text-xs font-bold">
                {DECISION_LABEL[curr.decision]}
              </Badge>
            </div>

            <div className="relative my-6 h-40 w-40">
              <svg viewBox="0 0 120 120" className="h-40 w-40 -rotate-90">
                <circle cx="60" cy="60" r={R} fill="none" stroke="#f1f5f9" strokeWidth="10" />
                <circle
                  cx="60"
                  cy="60"
                  r={R}
                  fill="none"
                  stroke={color}
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={`${(curr.trust_score / 100) * CIRC} ${CIRC}`}
                  className="transition-all duration-700"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-5xl font-extrabold tracking-tight text-slate-900">{curr.trust_score}</span>
                <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">/ 100</span>
              </div>
            </div>

            <div className="w-full pt-3 border-t border-slate-100 space-y-2 text-[11px] text-slate-500">
              <p>Model: <span className="font-mono font-semibold text-slate-700">{curr.model_version}</span></p>
              <p>Evaluated at <span className="font-mono font-semibold text-slate-700">{new Date(curr.timestamp).toLocaleTimeString()}</span></p>
              {curr.ml_signal !== null && (
                <p>ML signal: <span className="font-mono font-semibold text-slate-700">{curr.ml_signal}</span></p>
              )}
            </div>

            {curr.decision === 'STEP_UP' && (
              <BtnPrimary
                onClick={() => setOpenStepUp(true)}
                className="w-full justify-center text-xs py-2 mt-2 bg-amber-500 hover:bg-amber-600 text-white"
              >
                Perform Step-Up Re-auth
              </BtnPrimary>
            )}
          </div>

          {/* Component Breakdown & Why this score */}
          <div className="lg:col-span-2 space-y-6">
            <Panel title="Risk Components" subtitle="How the engine weighed each factor">
              <div className="divide-y divide-slate-100">
                {Object.entries(curr.components).length === 0 && (
                  <p className="py-3 text-xs text-slate-400">No component signals recorded yet.</p>
                )}
                {Object.entries(curr.components).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between py-3.5 text-xs">
                    <span className="font-semibold text-slate-800 capitalize">{k.replace(/_/g, ' ')}</span>
                    <div className="flex items-center gap-3">
                      <div className="h-1.5 w-32 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-brand-500 to-rose-500 transition-all"
                          style={{ width: `${Math.min(100, Math.max(0, v))}%` }}
                        />
                      </div>
                      <span className="w-8 text-right font-mono text-slate-600">{Math.round(v)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>

            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
              <button
                onClick={() => setOpenWhy(!openWhy)}
                className="flex w-full items-center justify-between text-xs font-bold text-slate-800"
              >
                <span>Why this score?</span>
                <ChevronDownIcon className={`h-4 w-4 transition-transform ${openWhy ? 'rotate-180' : ''}`} />
              </button>

              {openWhy && (
                <div className="mt-4 space-y-2 text-xs text-slate-600 animate-fade-up">
                  {curr.reasons.length === 0 && <p className="text-slate-400">No blocking reasons — trust is granted by default.</p>}
                  {curr.reasons.map((r, i) => (
                    <div key={i} className="flex items-center gap-2 rounded-xl bg-white p-3 border border-slate-200 shadow-sm">
                      <span className={`h-2 w-2 rounded-full ${curr.decision === 'ALLOW' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                      <span>{r}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <StepUpAuthModal isOpen={openStepUp} onClose={() => setOpenStepUp(false)} user={user} onVerified={() => { setOpenStepUp(false); load() }} />
    </div>
  )
}