import { useState } from 'react'
import { startRegistration, startAuthentication } from '@simplewebauthn/browser'
import { authApi, setAuth, type CurrentUser } from '../api'
import { BadgeCheckIcon, FingerprintIcon, LockIcon, ShieldIcon } from './icons'
import { BtnPrimary, Field, Input, Notice, Spinner } from './ui'

type Mode = 'login' | 'register' | 'reset'

export default function Login({ onLogin }: { onLogin: (user: CurrentUser) => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)

  function enter(res: { access_token: string; user: CurrentUser }) {
    setAuth(res.access_token, res.user)
    onLogin(res.user)
  }

  async function handleLogin() {
    setBusy(true)
    setError(null)
    try {
      enter(await authApi.login(email, password))
    } catch (e: any) {
      setError(e.message || 'Sign in failed.')
    } finally {
      setBusy(false)
    }
  }

  async function handleRegister() {
    setBusy(true)
    setError(null)
    try {
      enter(await authApi.register(email, password, fullName || undefined))
    } catch (e: any) {
      setError(e.message || 'Registration failed.')
    } finally {
      setBusy(false)
    }
  }

  async function handlePasskeyLogin() {
    setBusy(true)
    setError(null)
    try {
      const { options } = await authApi.loginStart(email)
      const credential = await startAuthentication(options)
      enter(await authApi.loginComplete(email, credential))
    } catch (e: any) {
      setError(e.message || 'Passkey sign in failed. Is a passkey registered for this account?')
    } finally {
      setBusy(false)
    }
  }

  async function handlePasskeyRegister() {
    setBusy(true)
    setError(null)
    try {
      const { options } = await authApi.registerStart(email)
      const credential = await startRegistration(options)
      enter(await authApi.registerComplete(email, credential))
    } catch (e: any) {
      setError(e.message || 'Passkey registration failed.')
    } finally {
      setBusy(false)
    }
  }

  async function handleResetRequest() {
    setBusy(true)
    setError(null)
    setInfo(null)
    try {
      const r = await authApi.resetRequest(email)
      if (r.reset_token) {
        setInfo(`Reset token generated for ${email}: ${r.reset_token.slice(0, 12)}… — contact your administrator in production.`)
        setResetToken(r.reset_token)
      } else {
        setInfo('If that account exists, a reset instruction was issued. In this development build the token is delivered to the account owner.')
        setMode('login')
      }
    } catch (e: any) {
      setError(e.message || 'Reset request failed.')
    } finally {
      setBusy(false)
    }
  }

  async function handleResetComplete() {
    setBusy(true)
    setError(null)
    try {
      await authApi.resetComplete(resetToken, password)
      setInfo('Password updated. Sign in with your new password.')
      setPassword('')
      setResetToken('')
      setMode('login')
    } catch (e: any) {
      setError(e.message || 'Reset failed.')
    } finally {
      setBusy(false)
    }
  }

  const footerRow = (
    <div className="mt-5 flex items-center gap-2 text-xs">
      {mode === 'login' ? (
        <>
          <button type="button" onClick={() => setMode('register')} className="font-bold text-brand-600 hover:text-brand-700">
            Create an account
          </button>
          <span className="text-slate-300">·</span>
          <button type="button" onClick={() => setMode('reset')} className="font-semibold text-slate-500 hover:text-slate-700">
            Forgot password?
          </button>
        </>
      ) : mode === 'register' ? (
        <button type="button" onClick={() => setMode('login')} className="font-bold text-brand-600 hover:text-brand-700">
          Back to sign in
        </button>
      ) : (
        <button type="button" onClick={() => setMode('login')} className="font-bold text-brand-600 hover:text-brand-700">
          Back to sign in
        </button>
      )}
    </div>
  )

  return (
    <div className="relative min-h-screen px-4 py-10 sm:px-6 flex items-center justify-center bg-slate-50">
      <div className="w-full max-w-5xl">
        <div className="grid w-full overflow-hidden rounded-3xl border border-ink-700 bg-white shadow-2xl animate-fade-up lg:grid-cols-[1.05fr_1fr]">
          {/* Left Decorative Branding Box */}
          <div className="relative hidden flex-col justify-between bg-gradient-to-br from-rose-50 via-white to-brand-50 p-10 lg:flex">
            <div className="relative flex items-center gap-3">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-rose-600 shadow-lg shadow-brand-600/25 text-white">
                <ShieldIcon className="h-7 w-7" />
              </div>
              <div>
                <p className="text-xl font-bold tracking-tight text-slate-900">TRUSTVAULT</p>
                <p className="text-xs font-medium text-slate-500">Verify once. Control access everywhere.</p>
              </div>
            </div>

            <div className="relative space-y-6">
              <h2 className="text-3xl font-extrabold leading-snug tracking-tight text-slate-900">
                Your credentials.
                <br />
                Your data.
                <br />
                <span className="text-brand-600">Your control.</span>
              </h2>

              <div className="space-y-3">
                <div className="flex items-start gap-3 rounded-2xl border border-slate-200/80 bg-white/80 p-3.5 shadow-sm">
                  <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
                    <BadgeCheckIcon className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-800">Verify once</p>
                    <p className="text-[11px] text-slate-500">Verified by issuers, instantly shareable with verifiers.</p>
                  </div>
                </div>

                <div className="flex items-start gap-3 rounded-2xl border border-slate-200/80 bg-white/80 p-3.5 shadow-sm">
                  <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
                    <LockIcon className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-800">Real-time Trust Protection</p>
                    <p className="text-[11px] text-slate-500">Catches suspicious devices and requests automatically.</p>
                  </div>
                </div>

                <div className="flex items-start gap-3 rounded-2xl border border-slate-200/80 bg-white/80 p-3.5 shadow-sm">
                  <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
                    <FingerprintIcon className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-800">Passwordless passkeys</p>
                    <p className="text-[11px] text-slate-500">WebAuthn-backed sign in with your device fingerprint.</p>
                  </div>
                </div>
              </div>
            </div>

            <p className="relative text-[11px] text-slate-400">Production-oriented identity & credential platform</p>
          </div>

          {/* Right Form Box */}
          <div className="p-8 sm:p-10 flex flex-col justify-center">
            <div className="lg:hidden mb-6 flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-rose-600 text-white shadow-md">
                <ShieldIcon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-lg font-bold tracking-tight text-slate-900">TRUSTVAULT</p>
                <p className="text-[11px] text-slate-500">Verify once. Control access everywhere.</p>
              </div>
            </div>

            {mode === 'login' && (
              <>
                <h1 className="text-2xl font-bold tracking-tight text-slate-900">Sign in to your account</h1>
                <p className="mt-1 text-xs text-slate-500">Use your password, or a passkey if you registered one.</p>

                <form
                  className="mt-6 space-y-3.5"
                  onSubmit={(e) => {
                    e.preventDefault()
                    handleLogin()
                  }}
                >
                  <Field label="Email address">
                    <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required />
                  </Field>
                  <Field label="Password">
                    <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Your password" required />
                  </Field>
                  <BtnPrimary className="w-full justify-center py-2.5" disabled={busy}>
                    {busy && <Spinner />}
                    {busy ? 'Signing in…' : 'Sign In'}
                  </BtnPrimary>
                </form>

                <div className="mt-3">
                  <button
                    type="button"
                    onClick={handlePasskeyLogin}
                    disabled={busy || !email}
                    className="flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 py-2.5 text-xs font-bold text-slate-800 transition hover:bg-slate-100 disabled:opacity-50"
                  >
                    {busy ? <Spinner /> : <FingerprintIcon className="h-4 w-4 text-brand-600" />}
                    {busy ? 'Authenticating…' : 'Sign in with Passkey'}
                  </button>
                </div>
              </>
            )}

            {mode === 'register' && (
              <>
                <h1 className="text-2xl font-bold tracking-tight text-slate-900">Create your account</h1>
                <p className="mt-1 text-xs text-slate-500">
                  New accounts sign in as <b>holder</b>. Issuers apply for organization verification after signing in.
                </p>

                <form
                  className="mt-6 space-y-3.5"
                  onSubmit={(e) => {
                    e.preventDefault()
                    handleRegister()
                  }}
                >
                  <Field label="Full name" hint="optional">
                    <Input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Your name" />
                  </Field>
                  <Field label="Email address">
                    <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required />
                  </Field>
                  <Field label="Password" hint="min 8 characters">
                    <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Choose a password" required minLength={8} />
                  </Field>
                  <BtnPrimary className="w-full justify-center py-2.5" disabled={busy}>
                    {busy && <Spinner />}
                    {busy ? 'Creating account…' : 'Create account'}
                  </BtnPrimary>
                </form>

                <div className="mt-3">
                  <button
                    type="button"
                    onClick={handlePasskeyRegister}
                    disabled={busy || !email}
                    className="flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 py-2.5 text-xs font-bold text-slate-800 transition hover:bg-slate-100 disabled:opacity-50"
                  >
                    {busy ? <Spinner /> : <FingerprintIcon className="h-4 w-4 text-brand-600" />}
                    {busy ? 'Creating passkey…' : 'Register with a Passkey'}
                  </button>
                </div>
              </>
            )}

            {mode === 'reset' && (
              <>
                <h1 className="text-2xl font-bold tracking-tight text-slate-900">Reset your password</h1>
                <p className="mt-1 text-xs text-slate-500">Request a reset token, then set a new password.</p>

                {!resetToken ? (
                  <div className="mt-6 space-y-3.5">
                    <Field label="Account email">
                      <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required />
                    </Field>
                    <BtnPrimary className="w-full justify-center py-2.5" onClick={handleResetRequest} disabled={busy || !email}>
                      {busy && <Spinner />}
                      {busy ? 'Requesting…' : 'Request reset token'}
                    </BtnPrimary>
                  </div>
                ) : (
                  <div className="mt-6 space-y-3.5">
                    <Field label="New password" hint="min 8 characters">
                      <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Choose a new password" required minLength={8} />
                    </Field>
                    <BtnPrimary className="w-full justify-center py-2.5" onClick={handleResetComplete} disabled={busy || !password}>
                      {busy && <Spinner />}
                      {busy ? 'Updating…' : 'Set new password'}
                    </BtnPrimary>
                  </div>
                )}
              </>
            )}

            {error && <Notice tone="red" className="mt-4">{error}</Notice>}
            {info && <Notice tone="green" className="mt-4">{info}</Notice>}

            <div className="mt-2">{footerRow}</div>
          </div>
        </div>
      </div>
    </div>
  )
}