import { useState } from 'react'
import type { ReactElement, SVGProps } from 'react'
import { setAuth, getCurrentUser } from './api'
import Login from './components/Login'
import DashboardPanel from './components/DashboardPanel'
import VerifyPanel from './components/VerifyPanel'
import TrustPanel from './components/TrustPanel'
import TimelinePanel from './components/TimelinePanel'
import CredentialsPanel from './components/CredentialsPanel'
import AssetsPanel from './components/AssetsPanel'
import AccessPanel from './components/AccessPanel'
import AuditPanel from './components/AuditPanel'
import {
  ShieldIcon,
  ActivityIcon,
  BadgeCheckIcon,
  FolderLockIcon,
  KeyIcon,
  FileTextIcon,
  LogOutIcon,
  DashboardIcon,
  QrCodeIcon,
} from './components/icons'
import { cn, Tip } from './components/ui'
import LanguageSwitcher from './components/LanguageSwitcher'
import { useLang, tr } from './i18n'

type Tab = 'dashboard' | 'verify' | 'trust' | 'timeline' | 'credentials' | 'assets' | 'access' | 'audit'

type IconCmp = (props: SVGProps<SVGSVGElement>) => ReactElement

const NAV_TAB: Record<Tab, string> = {
  dashboard: 'nav_dashboard',
  verify: 'nav_verify',
  trust: 'nav_trust',
  timeline: 'nav_timeline',
  credentials: 'nav_credentials',
  assets: 'nav_assets',
  access: 'nav_access',
  audit: 'nav_audit',
}

const NAV: { id: Tab; label: string; sub: string; icon: IconCmp; roles: string[]; tip: string }[] = [
  { id: 'dashboard', label: 'Dashboard', sub: 'Role-scoped overview + technical view', icon: DashboardIcon, roles: [], tip: 'Role-scoped summary: identity, credentials, assets/NFT custody, pending requests, security posture, quick actions (offline sync, device recovery, duress) and a Technical view for admins/auditors.' },
  { id: 'verify', label: 'Verify QR', sub: 'Short-lived credential verification', icon: QrCodeIcon, roles: [], tip: 'Verify a credential QR: paste the signed token the holder generated. The HMAC signature proves it came from TrustVault, the 5-minute expiry bounds it, and only minimal claims are disclosed. Open a shared link like /#/verify?token=... to auto-fill.' },
  { id: 'trust', label: 'Trust score', sub: 'Live Trust Engine state for your identity', icon: ShieldIcon, roles: [], tip: 'Shows your live 0-100 Trust Score, how it is calculated (Identity/Device/Behaviour/Context/History), decision (ALLOW/STEP_UP/RESTRICTED/DENY), and reason codes explaining what the engine sees right now.' },
  { id: 'timeline', label: 'Security timeline', sub: 'Security events and risk signals in real time', icon: ActivityIcon, roles: [], tip: "Streams security events in real time. When an attack happens, the timeline shows when trust drops, what triggered STEP_UP/RESTRICTED/DENY, and each event's risk signals." },
  { id: 'credentials', label: 'Credentials', sub: 'Hash-anchored verifiable credentials', icon: BadgeCheckIcon, roles: [], tip: 'Hash-only credentials issued once by an institution. Issuers can issue/revoke; holders see what is active/revoked and generate a short-lived QR to prove it. The blockchain only stores SHA-256 hashes, never raw documents.' },
  { id: 'assets', label: 'Assets & policies', sub: 'Encrypted documents, NFT custody, ABAC policies', icon: FolderLockIcon, roles: ['holder', 'issuer', 'admin'], tip: 'Upload a document → AES-256-GCM encrypted, SHA-256 hashed, optional ERC-721 NFT minted. Define ABAC policies (role + purpose + min trust + optional location/time). Transfer NFT ownership. Evaluate runs the 4-way decision pipeline with human explanations.' },
  { id: 'access', label: 'Access requests', sub: 'Purpose- and time-bound access grants', icon: KeyIcon, roles: ['holder', 'issuer', 'verifier', 'admin'], tip: 'Verifiers request access for a stated purpose. Holders approve with a time window (minutes) to create a purpose-bound, time-bound grant. Denials are recorded and visible.' },
  { id: 'audit', label: 'Audit trail', sub: 'Immutable on-chain audit anchors', icon: FileTextIcon, roles: ['holder', 'issuer', 'admin'], tip: 'High-value events are logged and anchored. Shows anchor status (pending/anchored), chain and tx hash. If configured with Sepolia RPC+key, anchors become real on-chain transactions.' },
]

const ROLE_STYLES: Record<string, string> = {
  admin: 'border-rose-300 bg-rose-50 text-rose-700',
  issuer: 'border-sky-300 bg-sky-50 text-sky-700',
  holder: 'border-emerald-300 bg-emerald-50 text-emerald-700',
  verifier: 'border-violet-300 bg-violet-50 text-violet-700',
  manager: 'border-orange-300 bg-orange-50 text-orange-700',
  auditor: 'border-cyan-300 bg-cyan-50 text-cyan-700',
  user: 'border-slate-300 bg-slate-100 text-slate-600',
}

function Brand() {
  const lang = useLang()
  return (
    <div className="flex items-center gap-3">
      <div className="relative grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-rose-600 shadow-lg shadow-brand-600/20">
        <ShieldIcon className="h-5 w-5 text-white" />
      </div>
      <div className="min-w-0">
        <p className="text-base font-bold tracking-tight text-slate-900">TrustVault</p>
        <p className="truncate text-[11px] text-slate-500">{tr(lang, 'tagline')}</p>
      </div>
    </div>
  )
}

function App() {
  const [user, setUser] = useState<any>(getCurrentUser())
  const [tab, setTab] = useState<Tab>('dashboard')
  const lang = useLang()

  if (!user) return <Login onLogin={setUser} />

  const visible = NAV.filter((t) => t.roles.length === 0 || t.roles.includes(user.role))
  const active = NAV.find((t) => t.id === tab) ?? NAV[0]

  function logout() {
    setAuth(null)
    setUser(null)
  }

  const initials = (user.email?.split('@')[0] ?? 'U').slice(0, 2).toUpperCase()

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-72 flex-col border-r border-ink-700 bg-white/80 backdrop-blur-xl lg:flex">
        <div className="px-6 py-6">
          <div className="flex items-center justify-between gap-3">
            <Brand />
            <LanguageSwitcher />
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3">
          <p className="px-3 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-widest text-slate-400">Workspace</p>
          {visible.map((t) => {
            const isActive = tab === t.id
            const Icon = t.icon
            return (
              <Tip key={t.id} label={t.tip} side="right">
                <button
                  onClick={() => setTab(t.id)}
                  className={cn(
                    'group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition',
                    isActive
                      ? 'bg-gradient-to-r from-brand-50 to-rose-50 text-slate-900 ring-1 ring-brand-200'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                  )}
                >
                  <Icon
                    className={cn(
                      'h-[18px] w-[18px] shrink-0 transition',
                      isActive ? 'text-brand-600' : 'text-slate-400 group-hover:text-slate-600',
                    )}
                  />
                  <span className="flex-1 text-left">{tr(lang, NAV_TAB[t.id])}</span>
                  {isActive && (
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-500 shadow-[0_0_10px] shadow-brand-500/60" />
                  )}
                </button>
              </Tip>
            )
          })}
        </nav>

        <div className="border-t border-ink-700 p-4">
          <div className="flex items-center gap-3 rounded-xl border border-ink-700 bg-white p-3 shadow-sm">
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-500/90 to-rose-600/90 text-xs font-bold text-white ring-1 ring-white/40">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-slate-800">{user.email}</p>
              <div className="mt-1 flex items-center gap-1.5">
                <span className={cn('rounded-full border px-1.5 py-px text-[10px] font-medium capitalize', ROLE_STYLES[user.role] ?? 'border-ink-600 bg-slate-100 text-slate-600')}>
                  {user.role}
                </span>
              </div>
            </div>
            <Tip label={tr(lang, 'signout_tip')}>
              <button
                onClick={logout}
                className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-ink-600 text-slate-500 transition hover:border-rose-400 hover:bg-rose-50 hover:text-rose-600"
              >
                <LogOutIcon className="h-4 w-4" />
              </button>
            </Tip>
          </div>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-30 border-b border-ink-700 bg-white/90 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            <Brand />
            <LanguageSwitcher />
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-3">
            {visible.map((t) => {
              const isActive = tab === t.id
              const Icon = t.icon
              return (
                <Tip key={t.id} label={t.tip} side="bottom">
                  <button
                    onClick={() => setTab(t.id)}
                    className={cn(
                      'flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition',
                      isActive ? 'bg-brand-50 text-brand-700 ring-1 ring-brand-300' : 'text-slate-600 hover:text-slate-900',
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {tr(lang, NAV_TAB[t.id])}
                  </button>
                </Tip>
              )
            })}
          </nav>
        </header>

        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-10">
          <div key={tab} className="animate-fade-up">
            <div className="mb-6 flex items-end justify-between gap-4">
              <div>
                <h1 className="text-xl font-bold tracking-tight text-slate-900">{tr(lang, NAV_TAB[active.id])}</h1>
                <p className="mt-0.5 text-sm text-slate-500">{active.sub}</p>
              </div>
              <Tip label="The Trust Engine and security timeline refresh live. The pulsing dot means it's polling updates from the backend.">
                <span className="hidden items-center gap-2 lg:flex">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-60" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-600" />
                  </span>
                  <span className="text-xs text-slate-500">{tr(lang, 'live')}</span>
                </span>
              </Tip>
            </div>

            {tab === 'dashboard' && <DashboardPanel />}
            {tab === 'verify' && <VerifyPanel />}
            {tab === 'trust' && <TrustPanel />}
            {tab === 'timeline' && <TimelinePanel />}
            {tab === 'credentials' && <CredentialsPanel userRole={user.role} />}
            {tab === 'assets' && <AssetsPanel onPipeline={() => {}} />}
            {tab === 'access' && <AccessPanel />}
            {tab === 'audit' && <AuditPanel />}
          </div>
        </main>
      </div>
    </div>
  )
}

export default App