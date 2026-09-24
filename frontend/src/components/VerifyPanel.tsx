import { useState } from 'react'
import { qrApi } from '../api'
import { Badge, Notice, Panel, BtnPrimary, Field, Textarea, Tip, SpeakerButton } from './ui'
import { QrCodeIcon, CheckIcon } from './icons'
import { useLang, tr } from '../i18n'

type QrResult = {
  id: string
  valid: boolean
  status: string
  hash_match: boolean
  holder_did: string | null
  type: string | null
  issuer_id: string | null
  issued_at: string | null
  purpose: string | null
  expires_at: string | null
  selective_disclosure_ready: boolean
  explanation: string | null
}

function tokenFromHash() {
  try {
    const m = window.location.hash.match(/[?&]token=([^&]+)/)
    return m ? decodeURIComponent(m[1]) : ''
  } catch {
    return ''
  }
}

export default function VerifyPanel() {
  const auto = tokenFromHash()
  const [token, setToken] = useState(auto)
  const [result, setResult] = useState<QrResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const lang = useLang()

  async function verify() {
    setBusy(true)
    setErr(null)
    setResult(null)
    try {
      setResult(await qrApi.verify(token.trim()))
    } catch (e: any) {
      setErr('Verification failed: ' + (e.message ?? 'unknown error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <Panel
        title={tr(lang, 'verify_title')}
        subtitle={tr(lang, 'verify_paste')}
        icon={<QrCodeIcon className="h-5 w-5" />}
        help="A QR token is a short-lived permission slip that proves a certificate is real and only shows the bare minimum - never the certificate itself. It works for up to 5 minutes and expires automatically."
      >
        <div className="space-y-3.5">
          <Field label="QR token" hint="from the holder's QR or the certificates tab">
            <Textarea
              rows={5}
              className="font-mono text-xs"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="paste the token shown in the QR link"
            />
          </Field>
          <div className="flex flex-wrap items-center gap-2">
            <BtnPrimary onClick={verify} disabled={!token.trim() || busy}>
              {busy ? tr(lang, 'verify_btn_busy') : tr(lang, 'verify_btn')}
            </BtnPrimary>
            {auto && (
              <Tip label="This token was picked up from a shared QR link (#/verify?token=...).">
                <Badge tone="blue">token from QR link</Badge>
              </Tip>
            )}
          </div>
          {err && <Notice tone="red">{err}</Notice>}
        </div>
      </Panel>

      <Panel
        title={tr(lang, 'verify_result_title')}
        subtitle={tr(lang, 'verify_result_sub')}
        icon={<CheckIcon className="h-5 w-5" />}
      >
        {!result ? (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
            <div className="grid h-14 w-14 place-items-center rounded-2xl border border-slate-200 bg-slate-50 text-slate-400">
              <QrCodeIcon className="h-7 w-7" />
            </div>
            <p className="text-sm font-medium text-slate-600">{tr(lang, 'verify_none')}</p>
            <p className="max-w-xs text-xs text-slate-400">
              Scan a holder's QR or paste its token here. The result proves the certificate exists, was issued by a
              trusted office, and has not been cancelled.
            </p>
          </div>
        ) : (
          <div
            className={
              result.valid
                ? 'rounded-xl border border-emerald-200 bg-emerald-50 p-4'
                : 'rounded-xl border border-rose-200 bg-rose-50 p-4'
            }
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={result.valid ? 'green' : 'red'} dot>
                {result.valid ? tr(lang, 'verify_valid') : tr(lang, 'verify_invalid')}
              </Badge>
              <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">status · {result.status}</span>
            </div>
            {result.explanation && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium text-slate-800">{result.explanation}</p>
                <SpeakerButton text={result.explanation} tone={result.valid ? 'green' : 'red'} />
              </div>
            )}
            <dl className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {[
                ['Certificate id', result.id],
                ['Type', result.type],
                ['Holder', result.holder_did],
                ['Issued by', result.issuer_id],
                ['Issued', result.issued_at ? new Date(result.issued_at).toLocaleString() : null],
                ['Purpose', result.purpose],
                ['Expires', result.expires_at ? new Date(result.expires_at).toLocaleTimeString() : null],
                ['Shows only the minimum', result.selective_disclosure_ready ? 'yes' : 'no'],
              ].map(([k, v]) => (
                <div key={String(k)} className="rounded-lg border border-white/60 bg-white/70 px-3 py-2">
                  <dt className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{k}</dt>
                  <dd className="mt-0.5 truncate font-mono text-xs text-slate-800">{String(v ?? '-')}</dd>
                </div>
              ))}
            </dl>
            {!result.valid && result.status === 'invalid_token' && (
              <Notice tone="red" className="mt-3">
                The token is missing, tampered with, or expired. Ask the holder to refresh their QR link.
              </Notice>
            )}
          </div>
        )}
      </Panel>
    </div>
  )
}