import { useState } from 'react'
import { CheckIcon, QrCodeIcon, XIcon } from './icons'
import { BtnGhost, BtnPrimary, Field, Notice, Select, Spinner } from './ui'
import { credentialsApi, type Credential, type QrGenerate } from '../api'

export default function ShareCredentialModal({
  cred,
  onClose,
}: {
  cred: Credential | null
  onClose: () => void
}) {
  const [purpose, setPurpose] = useState('Verification')
  const [busy, setBusy] = useState(false)
  const [qr, setQr] = useState<QrGenerate | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  if (!cred) return null

  async function handleGenerate() {
    if (!cred) return
    setBusy(true)
    setError(null)
    setMsg(null)
    try {
      setQr(await credentialsApi.generateQr(cred.id, purpose, 10))
      setMsg('Real time-limited verification token created. It expires in 10 minutes.')
    } catch (e: any) {
      setError(e.message || 'Could not create a shareable token.')
    } finally {
      setBusy(false)
    }
  }

  const copyLink = () => {
    if (!qr) return
    navigator.clipboard?.writeText(window.location.origin + qr.qr_url)
    setMsg('Verification link copied to clipboard.')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-lg rounded-3xl border border-ink-700 bg-white p-6 shadow-2xl animate-fade-up">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <XIcon className="h-5 w-5" />
        </button>

        <h2 className="text-lg font-bold text-slate-900">Share Credential</h2>
        <p className="text-xs text-slate-500 mb-5">
          Generate a real, short-lived verification token for <b className="text-slate-700">{cred.title ?? cred.type}</b>.
          Anyone with the link or QR can verify its status on the public page.
        </p>

        {!qr ? (
          <div className="space-y-4">
            <Field label="Verification purpose">
              <Select value={purpose} onChange={(e) => setPurpose(e.target.value)}>
                <option value="Verification">General verification</option>
                <option value="Employment Verification">Employment verification</option>
                <option value="Education Verification">Education verification</option>
                <option value="Internship">Internship</option>
                <option value="Other">Other</option>
              </Select>
            </Field>

            {error && <Notice tone="red">{error}</Notice>}

            <div className="flex justify-end gap-2 pt-2">
              <BtnGhost onClick={onClose}>Cancel</BtnGhost>
              <BtnPrimary onClick={handleGenerate} disabled={busy || statusNotShareable(cred.status)}>
                {busy && <Spinner />}
                {busy ? 'Generating…' : 'Generate Share Link'}
              </BtnPrimary>
            </div>
            {statusNotShareable(cred.status) && (
              <p className="text-[11px] text-rose-600">Only active credentials can be shared.</p>
            )}
          </div>
        ) : (
          <div className="py-2 space-y-4 text-center">
            <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-emerald-100 text-emerald-600 shadow-md">
              <CheckIcon className="h-8 w-8" />
            </div>

            <div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">
                Token ready · expires {new Date(qr.expires_at).toLocaleTimeString()}
              </span>
              <p className="text-xs text-slate-500 mt-2">
                Share this link, or scan the generated QR back in the credential list.
              </p>
            </div>

            <img
              src={`/api/verify/${encodeURIComponent(qr.qr_token)}/qr`}
              alt="Shareable QR"
              className="mx-auto h-40 w-40 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm"
            />

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-left font-mono text-xs text-slate-700 break-all">
              <p className="text-[10px] text-slate-400 font-sans mb-1">VERIFICATION LINK</p>
              {window.location.origin + qr.qr_url}
            </div>

            {msg && <Notice tone="green">{msg}</Notice>}

            <div className="grid grid-cols-2 gap-3 pt-2">
              <BtnGhost className="justify-center gap-2" onClick={copyLink}>
                Copy Link
              </BtnGhost>
              <BtnPrimary className="justify-center gap-2" onClick={() => setQr(null)}>
                <QrCodeIcon className="h-4 w-4" />
                Done
              </BtnPrimary>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function statusNotShareable(status: string): boolean {
  return status !== 'active'
}