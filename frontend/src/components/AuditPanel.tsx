import { useEffect, useState } from 'react'
import { api, type Asset } from '../api'
import { Badge, EmptyState, Notice, Panel, BtnPrimary, Select, decisionTone, cn } from './ui'
import { CheckIcon, FileTextIcon, XIcon, AlertIcon, InfoIcon } from './icons'

type AuditRow = {
  event_id: string
  event_type: string
  trust_score: number | null
  decision: string | null
  risk_signals: Record<string, any>
  created_at: string
  anchor: { tx_hash: string; chain: string; status: string } | null
}

export default function AuditPanel() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [selected, setSelected] = useState('')
  const [rows, setRows] = useState<AuditRow[]>([])
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => {
    api.get<Asset[]>('/assets').then(setAssets).catch(() => {})
  }, [])

  async function show() {
    setMsg(null)
    try {
      setRows(await api.get<AuditRow[]>(`/audit/${selected}`))
    } catch (e: any) {
      setMsg(`Failed: ${e.message}`)
      setRows([])
    }
  }

  return (
    <Panel
      title="Audit trail"
      subtitle="Full history of high-value events with on-chain anchor status"
      icon={<FileTextIcon className="h-5 w-5" />}
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <Select value={selected} onChange={(e) => setSelected(e.target.value)} className="sm:max-w-xs">
          <option value="">Select asset…</option>
          {assets.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({a.id.slice(0, 8)}…)
            </option>
          ))}
        </Select>
        <BtnPrimary onClick={show} disabled={!selected}>
          Show audit
        </BtnPrimary>
      </div>

      {rows.length === 0 && selected && (
        <div className="mt-5">
          <EmptyState
            icon={<FileTextIcon className="h-5 w-5" />}
            title="No logged events"
            hint="No high-value events have been recorded for this asset yet."
          />
        </div>
      )}

      <div className="mt-5 space-y-3">
        {rows.map((r) => {
          const tone = r.decision ? decisionTone(r.decision) : 'slate'
          const Icon =
            r.decision === 'ALLOW' ? CheckIcon : r.decision === 'STEP_UP' ? AlertIcon : r.decision === 'RESTRICTED' ? InfoIcon : XIcon
          return (
            <div key={r.event_id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300">
              <div className="flex flex-wrap items-center gap-2">
                <div
                  className={cn(
                    'grid h-7 w-7 place-items-center rounded-lg border',
                    tone === 'green'
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-600'
                      : tone === 'amber'
                        ? 'border-amber-200 bg-amber-50 text-amber-600'
                        : tone === 'violet'
                          ? 'border-violet-200 bg-violet-50 text-violet-600'
                          : 'border-rose-200 bg-rose-50 text-rose-600',
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <span className="rounded-md border border-brand-200 bg-brand-50 px-1.5 py-0.5 font-mono text-[11px] text-brand-700">
                  {r.event_type}
                </span>
                {r.decision && <Badge tone={tone}>{r.decision}</Badge>}
                {r.trust_score !== null && (
                  <span className="font-mono text-[11px] text-slate-500">trust {r.trust_score}</span>
                )}
                <span className="ml-auto font-mono text-[10px] text-slate-500">
                  {new Date(r.created_at).toLocaleString()}
                </span>
              </div>

              {r.anchor && (
                <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  <Badge tone={r.anchor.status === 'anchored' ? 'green' : 'amber'} dot>
                    {r.anchor.status}
                  </Badge>
                  <span className="font-mono text-[10px] text-slate-500">
                    {r.anchor.chain} · {r.anchor.tx_hash}
                  </span>
                </div>
              )}

              {Object.keys(r.risk_signals ?? {}).length > 0 && (
                <details className="mt-2 group">
                  <summary className="cursor-pointer text-[11px] text-slate-500 transition hover:text-slate-700">
                    Risk signals
                  </summary>
                  <pre className="mt-2 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-2.5 font-mono text-[10px] leading-relaxed text-slate-500">
                    {JSON.stringify(r.risk_signals, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          )
        })}
      </div>

      {msg && (
        <Notice tone="red" className="mt-4">
          {msg}
        </Notice>
      )}
    </Panel>
  )
}