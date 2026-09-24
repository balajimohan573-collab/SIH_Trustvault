import { useState } from 'react'
import { qrApi } from '../api'
import { Badge, Notice, Panel, BtnPrimary, Field, Textarea, Tip } from './ui'
import { QrCodeIcon, CheckIcon } from './icons'

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
        title="Verify a credential QR"
        subtitle="Paste the short-lived token the holder generated"
        icon={<QrCodeIcon className="h-5 w-5" />}
        help="The QR token is an HMAC-signed, short-lived JWT bound to exactly one credential + purpose. Anyone with the token can verify it: the signature proves it came from this platform and the 5-minute expiry bounds its lifetime. Only minimal claims are disclosed (validity, type, holder DID, purpose) - never the raw document."
      >
        <div className="space-y-3.5">
          <Field label="QR token" hint="from the holder's QR or the Credentials tab">
            <Textarea
              rows={5}
              className="font-mono text-xs"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="eyJhbGciOiJIUzI1NiIs..."
            />
          </Field>
          <div className="flex flex-wrap items-center gap-2">
            <BtnPrimary onClick={verify} disabled={!token.trim() || busy}>
              {busy ? 'Verifying...' : 'Verify credential'}
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
        title="Verification result"
        subtitle="Signature + short expiry = forward proof; status = live registry state"
        icon={<CheckIcon className="h-5 w-5" />}
      >
        {!result ? (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
            <div className="grid h-14 w-14 place-items-center rounded-2xl border border-slate-200 bg-slate-50 text-slate-400">
              <QrCodeIcon className="h-7 w-7" />
            </div>
            <p className="text-sm font-medium text-slate-600">No verification yet</p>
            <p className="max-w-xs text-xs text-slate-400">
              Scan a holder's QR or paste its token here. The result proves the credential exists, is signed by the
              platform, and has not been revoked.
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
                {result.valid ? 'VALID' : 'INVALID'}
              </Badge>
              <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">status · {result.status}</span>
            </div>
            {result.explanation && <p className="mt-2 text-sm font-medium text-slate-800">{result.explanation}</p>}
            <dl className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {[
                ['Credential id', result.id],
                ['Type', result.type],
                ['Holder DID', result.holder_did],
                ['Issuer id', result.issuer_id],
                ['Issued', result.issued_at ? new Date(result.issued_at).toLocaleString() : null],
                ['Purpose', result.purpose],
                ['Expires', result.expires_at ? new Date(result.expires_at).toLocaleTimeString() : null],
                ['Selective disclosure ready', result.selective_disclosure_ready ? 'yes' : 'no'],
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