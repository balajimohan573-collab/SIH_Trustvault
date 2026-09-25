import { useState } from 'react'
import { BadgeCheckIcon, LockIcon, ShieldIcon, XIcon } from './icons'
import { BtnGhost, BtnPrimary, Field, Input, Notice, Spinner } from './ui'
import { authApi, type CurrentUser } from '../api'

export default function StepUpAuthModal({
  isOpen,
  onClose,
  user,
  onVerified,
}: {
  isOpen: boolean
  onClose: () => void
  user: CurrentUser
  onVerified: () => void
}) {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  if (!isOpen) return null

  const handleVerify = async () => {
    setBusy(true)
    setError(null)
    try {
      // Real step-up: re-authenticate with the account password. The backend
      // validates it and records a fresh login/device security event.
      await authApi.login(user.email, password)
      setSuccess(true)
    } catch (e: any) {
      setError(e.message || 'Re-authentication failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-md rounded-3xl border border-ink-700 bg-white p-6 shadow-2xl animate-fade-up">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <XIcon className="h-5 w-5" />
        </button>

        {!success ? (
          <div className="text-center space-y-4">
            <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-amber-100 text-amber-600 shadow-md">
              <ShieldIcon className="h-7 w-7" />
            </div>

            <div>
              <h3 className="text-lg font-bold text-slate-900">Additional Verification Required</h3>
              <p className="mt-1 text-xs leading-relaxed text-slate-600">
                The Trust Engine is asking for stronger proof before granting access. Re-authenticate with your account password
                to restore your full trust standing.
              </p>
            </div>

            <div className="space-y-3 pt-2 text-left">
              <Field label="Current password">
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Your password"
                  autoFocus
                />
              </Field>
              {error && <Notice tone="red">{error}</Notice>}
              <BtnPrimary className="w-full justify-center" onClick={handleVerify} disabled={busy || !password}>
                {busy && <Spinner />}
                {busy ? 'Verifying…' : 'Verify identity'}
              </BtnPrimary>
              <BtnGhost onClick={onClose} className="w-full justify-center">
                Cancel
              </BtnGhost>
            </div>
          </div>
        ) : (
          <div className="py-4 text-center space-y-4">
            <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-emerald-100 text-emerald-600 shadow-lg">
              <BadgeCheckIcon className="h-9 w-9" />
            </div>

            <div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">
                <LockIcon className="h-3.5 w-3.5" />
                Re-authentication recorded
              </span>
              <p className="text-sm font-bold text-slate-900 mt-2">Identity Confirmed</p>
              <p className="text-xs text-slate-500 mt-1">A fresh login security event was recorded. Refresh the trust state to see the updated score.</p>
            </div>

            <div className="pt-2">
              <BtnPrimary
                className="w-full justify-center"
                onClick={() => {
                  onVerified()
                }}
              >
                Reload Trust State
              </BtnPrimary>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
