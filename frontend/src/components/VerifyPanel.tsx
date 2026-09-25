import { useCallback, useEffect, useState } from 'react'
import { CheckIcon, ChevronDownIcon, QrCodeIcon, ShieldIcon } from './icons'
import { Badge, BtnPrimary, EmptyState, Field, Panel, Spinner, Textarea, decisionTone } from './ui'
import { verifyApi } from '../api'

type VerifyResult = Awaited<ReturnType<typeof verifyApi.byToken>>

const RESULT_LABEL: Record<string, string> = {
  VERIFIED: 'Verified Authentic',
  INVALID: 'Not Recognized',
  EXPIRED: 'Expired',
  REVOKED: 'Revoked',
}

export default function VerifyPanel({ initialToken }: { initialToken?: string | null }) {
  const [token, setToken] = useState(initialToken ?? '')
  const [result, setResult] = useState<VerifyResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showProof, setShowProof] = useState(false)

  const handleVerify = useCallback(async (t?: string) => {
    const value = (t ?? token).trim()
    if (!value) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await verifyApi.byToken(value)
      setResult(res)
      if (res.reason) setError(null)
    } catch (e: any) {
      setError(e.message || 'Verification failed.')
    } finally {
      setBusy(false)
    }
  }, [token])

  useEffect(() => {
    if (initialToken) {
      setToken(initialToken)
      handleVerify(initialToken)
    }
  }, [initialToken, handleVerify])

  const ok = result?.valid === true
  const tone = result ? (ok ? 'green' : result.checks?.['not_revoked'] === false ? 'red' : 'amber') : 'slate'

  return (
    <div className="mx-auto max-w-4xl space-y-6 animate-fade-up">
      {/* Header banner */}
      <div className="rounded-3xl border border-ink-700 bg-gradient-to-r from-brand-50 via-rose-50 to-white p-6 sm:p-8 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-rose-600 shadow-xl shadow-brand-600/25 text-white">
              <ShieldIcon className="h-8 w-8" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">TRUSTVAULT Verification</h1>
              <p className="text-xs text-slate-500 mt-1">Public, tamper-proof credential verification</p>
            </div>
          </div>
          {result && (
            <div className={`flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-bold border ${tone === 'green' ? 'bg-emerald-100 text-emerald-800 border-emerald-200' : tone === 'red' ? 'bg-rose-100 text-rose-800 border-rose-200' : 'bg-amber-100 text-amber-800 border-amber-200'}`}>
              <span className="h-2 w-2 rounded-full bg-current animate-pulse" />
              {RESULT_LABEL[result.result] ?? result.status}
            </div>
          )}
        </div>
      </div>

      {/* Main Verification View */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {/* Quick Verify Input Panel */}
        <div className="md:col-span-1 space-y-4">
          <Panel title="Verify Link / Token" icon={<QrCodeIcon className="h-5 w-5" />}>
            <div className="space-y-3">
              <Field label="Token or URL">
                <Textarea
                  rows={4}
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Paste QR verification token or link..."
                  className="font-mono text-xs"
                />
              </Field>
              <BtnPrimary className="w-full justify-center" onClick={() => handleVerify()} disabled={busy}>
                {busy && <Spinner />}
                {busy ? 'Verifying…' : 'Verify Credential'}
              </BtnPrimary>
            </div>
          </Panel>

          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5 text-center">
            {result && token ? (
              // The QR image is served by the backend for this live token.
              <img
                src={verifyApi.qrUrl(token.trim())}
                alt="Live credential QR"
                className="mx-auto h-40 w-40 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm"
              />
            ) : (
              <QrCodeIcon className="mx-auto h-24 w-24 text-slate-800" />
            )}
            <p className="mt-2 text-xs font-semibold text-slate-700">
              {result && token ? 'Live QR for this verification token' : 'Live QR Verification'}
            </p>
            <p className="text-[11px] text-slate-500 mt-0.5">Scanned QR codes map directly to this proof page.</p>
          </div>
          {error && <p className="text-xs font-semibold text-rose-600 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">{error}</p>}
        </div>

        {/* Verification Result Card */}
        <div className="md:col-span-2 space-y-4">
          {!result && !error && (
            <EmptyState
              icon={<QrCodeIcon className="h-6 w-6" />}
              title="No verification yet"
              hint="Paste a verification token (or open a shared credential link) to see the live result."
            />
          )}
          {result && (
            <div className={`rounded-3xl border bg-white p-6 shadow-sm space-y-6 ${ok ? 'border-emerald-200' : 'border-slate-200'}`}>
              <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                <div className="flex items-center gap-3">
                  <div className={`grid h-12 w-12 place-items-center rounded-2xl ${ok ? 'bg-emerald-100 text-emerald-600' : 'bg-rose-100 text-rose-600'}`}>
                    <CheckIcon className="h-7 w-7" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-slate-900">{RESULT_LABEL[result.result] ?? result.result}</h2>
                    <p className="text-xs text-slate-500">Integrity and status as recorded by the issuer</p>
                  </div>
                </div>
                <Badge tone={decisionTone(ok ? 'ALLOW' : 'DENY')} dot className="px-3 py-1 text-xs">
                  {result.status}
                </Badge>
              </div>

              {/* Verified Details Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">Credential</span>
                  <p className="mt-1 text-sm font-bold text-slate-900">{result.type ?? '—'}</p>
                </div>
                <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">Holder</span>
                  <p className="mt-1 text-sm font-bold text-slate-900">{result.holder_name ?? result.holder_did ?? '—'}</p>
                </div>
                <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">Issuer</span>
                  <p className="mt-1 text-sm font-bold text-slate-900">{result.issuer_org ?? '—'}</p>
                </div>
                <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">Purpose</span>
                  <p className="mt-1 text-sm font-bold text-slate-900">{result.purpose ?? 'Credential verification'}</p>
                </div>
                <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">Issued</span>
                  <p className="mt-1 text-sm font-bold text-slate-900">
                    {result.issued_at ? new Date(result.issued_at).toLocaleDateString() : '—'}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">Expiry</span>
                  <p className="mt-1 text-sm font-bold text-slate-900">{result.expiry_date ?? 'No expiry'}</p>
                </div>
              </div>

              {/* Public claims (selective disclosure) */}
              {Object.keys(result.public_claims ?? {}).length > 0 && (
                <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4 text-xs">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">Disclosed claims</span>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {Object.entries(result.public_claims).map(([k, v]) => (
                      <span key={k} className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 font-semibold text-slate-700">
                        {k.replace(/_/g, ' ')}: {v}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {!ok && result.reason && (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-700">
                  {result.reason}
                </div>
              )}

              {/* Integrity checks collapsible */}
              <div className="pt-2">
                <button
                  onClick={() => setShowProof(!showProof)}
                  className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition"
                >
                  <span>View integrity checks</span>
                  <ChevronDownIcon className={`h-4 w-4 transition-transform ${showProof ? 'rotate-180' : ''}`} />
                </button>
                {showProof && (
                  <div className="mt-3 space-y-1.5 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs animate-fade-up">
                    {Object.entries(result.checks ?? {}).map(([k, v]) => (
                      <div key={k} className="flex items-center justify-between">
                        <span className="font-mono text-slate-500">{k.replace(/_/g, ' ')}</span>
                        <span className={`font-bold ${v ? 'text-emerald-600' : 'text-rose-600'}`}>{v ? 'pass' : 'fail'}</span>
                      </div>
                    ))}
                    <p className="pt-1 text-[10px] text-slate-400">Credential: {result.credential_id ?? '—'}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}