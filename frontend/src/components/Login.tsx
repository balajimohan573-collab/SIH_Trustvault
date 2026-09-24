import { useState } from 'react'
import { api, authApi, setAuth } from '../api'
import { BadgeCheckIcon, ChevronRightIcon, FingerprintIcon, LockIcon, ShieldIcon } from './icons'
import { BtnPrimary, Field, Input, Notice, Spinner, cn, Tip } from './ui'

const DEMO_ACCOUNTS = [
  { email: 'issuer@trustvault.example', label: 'Issuer', desc: 'An institution that issues credentials', dot: 'bg-sky-500', tip: 'Sign in as Issuer to issue, verify and revoke hash-only credentials.' },
  { email: 'holder@trustvault.example', label: 'Holder', desc: 'A user with encrypted assets & policies', dot: 'bg-emerald-500', tip: 'Sign in as Holder to upload encrypted documents, create ABAC policies, and approve/deny access requests.' },
  { email: 'verifier@trustvault.example', label: 'Verifier', desc: 'An employer requesting scoped access', dot: 'bg-violet-500', tip: 'Sign in as Verifier to request purpose-scoped, time-bound access and download when allowed.' },
  { email: 'admin@trustvault.example', label: 'Admin', desc: 'Platform administrator with override', dot: 'bg-rose-500', tip: 'Sign in as Admin to view all areas and use the documented, audited override for recovery scenarios.' },
]

const FEATURES = [
  { icon: <BadgeCheckIcon className="h-4 w-4" />, title: 'Verify once', text: 'Institutions issue hash-anchored credentials a single time.', tip: 'You don’t re-verify per request — trust is re-evaluated live from context and policy.' },
  { icon: <LockIcon className="h-4 w-4" />, title: 'Privacy by design', text: 'Documents stay AES-256-GCM encrypted — never raw on chain.', tip: 'Only SHA-256 hashes and audit/decision anchors go on-chain; ciphertext stays local.' },
  { icon: <FingerprintIcon className="h-4 w-4" />, title: 'Context-aware access', text: 'The Trust Engine re-evaluates every request against evolving risk.', tip: 'Identity + Device + Behaviour + Context + History combine into an explainable 0–100 score.' },
  { icon: <ShieldIcon className="h-4 w-4" />, title: 'Immutably auditable', text: 'High-value events are anchored to the blockchain.', tip: 'Every high-value decision/event is logged with on-chain anchor status and a tx hash.' },
]

export default function Login({ onLogin }: { onLogin: (user: any) => void }) {
  const [email, setEmail] = useState(DEMO_ACCOUNTS[1].email)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function signIn(mail: string) {
    setBusy(true)
    setError(null)
    try {
      const res = await authApi.devLogin(mail)
      setAuth(res.access_token, res.user)
      const me = await api.get<any>('/auth/me')
      setAuth(res.access_token, me)
      onLogin(me)
    } catch (e: any) {
      setError(e?.message ?? 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative min-h-screen px-4 py-10 sm:px-6">
      <div className="mx-auto grid w-full max-w-5xl overflow-hidden rounded-3xl border border-ink-700 bg-white shadow-xl shadow-slate-200/70 animate-fade-up lg:grid-cols-[1.05fr_1fr]">
        <div className="relative hidden flex-col justify-between bg-gradient-to-br from-rose-50 via-white to-white p-10 lg:flex">
          <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-rose-500/10 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-20 -left-10 h-56 w-56 rounded-full bg-brand-500/10 blur-3xl" />

          <div className="relative flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-rose-600 shadow-lg shadow-brand-600/25">
              <ShieldIcon className="h-6 w-6 text-white" />
            </div>
            <div>
              <p className="text-lg font-bold tracking-tight text-slate-900">TrustVault</p>
              <p className="text-xs text-slate-500">Verify once. Control access everywhere.</p>
            </div>
          </div>

          <div className="relative space-y-5">
            <p className="text-2xl font-bold leading-snug tracking-tight text-slate-900">
              Blockchain-anchored,
              <br />
              privacy-preserving
              <br />
              identity &amp; access control.
            </p>
            <div className="space-y-3.5">
              {FEATURES.map((f) => (
                <Tip key={f.title} label={f.tip} side="right">
                  <div className="flex cursor-help items-start gap-3 rounded-xl border border-ink-700 bg-white/80 p-3 shadow-sm">
                    <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-brand-100 bg-brand-50 text-brand-600">
                      {f.icon}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-800">{f.title}</p>
                      <p className="text-xs leading-relaxed text-slate-500">{f.text}</p>
                    </div>
                  </div>
                </Tip>
              ))}
            </div>
          </div>

          <p className="relative text-[11px] text-slate-400">
            Demo build · runs free on Sepolia testnet with WebAuthn / passkey support
          </p>
        </div>

        <div className="p-8 sm:p-12">
          <div className="lg:hidden">
            <div className="mb-6 flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-rose-600 shadow-lg shadow-brand-600/25">
                <ShieldIcon className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-base font-bold tracking-tight text-slate-900">TrustVault</p>
                <p className="text-[11px] text-slate-500">Verify once. Control access everywhere.</p>
              </div>
            </div>
          </div>

          <h1 className="text-xl font-bold tracking-tight text-slate-900">Sign in to get started</h1>
          <p className="mt-1 text-sm text-slate-500">
            Pick a role below to enter the security flow, or type your own demo email.
          </p>

          <form
            className="mt-6 space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              signIn(email)
            }}
          >
            <Field label="Email" hint="dev-login fallback (no password needed)">
              <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@trustvault.example" />
            </Field>
            <BtnPrimary className="w-full" disabled={busy}>
              {busy && <Spinner />}
              {busy ? 'Signing in…' : 'Sign in'}
            </BtnPrimary>
          </form>

          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-ink-700" />
            <span className="text-[11px] uppercase tracking-widest text-slate-400">or demo role</span>
            <div className="h-px flex-1 bg-ink-700" />
          </div>

          <div className="space-y-2">
            {DEMO_ACCOUNTS.map((a) => (
              <Tip key={a.email} label={a.tip} side="bottom">
                <button
                  disabled={busy}
                  className={cn(
                    'group flex w-full items-center gap-3 rounded-xl border border-ink-700 bg-white px-4 py-3 text-left shadow-sm transition',
                    'hover:border-brand-400 hover:bg-brand-50/60 disabled:cursor-wait disabled:opacity-60',
                  )}
                  onClick={() => signIn(a.email)}
                >
                  <span className={cn('h-2 w-2 shrink-0 rounded-full', a.dot)} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-slate-800">{a.label}</span>
                      <span className="font-mono text-[10px] text-slate-500">{a.email}</span>
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-slate-500">{a.desc}</span>
                  </span>
                  <ChevronRightIcon className="h-4 w-4 shrink-0 text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-brand-600" />
                </button>
              </Tip>
            ))}
          </div>

          <Notice tone="slate" className="mt-6">
            <span className="font-medium">Why demo roles?</span> The dev-login fallback lets the whole security
            flow run without a hardware authenticator. The production path uses WebAuthn passkeys ({' '}
            <code className="font-mono text-[10px] text-rose-600">register/start → complete → login/start → complete</code>).
          </Notice>

          {error && (
            <Notice tone="red" className="mt-3">
              {error}
            </Notice>
          )}
        </div>
      </div>
    </div>
  )
}