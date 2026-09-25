import { useEffect, useState } from 'react'
import type { ReactElement, SVGProps } from 'react'
import { authApi, setAuth, getCurrentUser, type CurrentUser } from './api'
import Login from './components/Login'
import DashboardPanel from './components/DashboardPanel'
import VerifyPanel from './components/VerifyPanel'
import TrustPanel from './components/TrustPanel'
import TimelinePanel from './components/TimelinePanel'
import CredentialsPanel from './components/CredentialsPanel'
import AccessPanel from './components/AccessPanel'
import AuditPanel from './components/AuditPanel'
import SettingsPanel from './components/SettingsPanel'
import {
  ShieldIcon,
  ActivityIcon,
  BadgeCheckIcon,
  KeyIcon,
  DashboardIcon,
  QrCodeIcon,
  LogOutIcon,
  SettingsIcon,
  UserIcon,
} from './components/icons'
import { cn } from './components/ui'

type Tab = 'dashboard' | 'verify' | 'trust' | 'timeline' | 'credentials' | 'access' | 'audit' | 'settings'

type IconCmp = (props: SVGProps<SVGSVGElement>) => ReactElement

const NAV: { id: Tab; label: string; icon: IconCmp; roles: string[] }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: DashboardIcon, roles: [] },
  { id: 'credentials', label: 'My Credentials', icon: BadgeCheckIcon, roles: [] },
  { id: 'access', label: 'Access', icon: KeyIcon, roles: [] },
  { id: 'trust', label: 'Security', icon: ShieldIcon, roles: [] },
  { id: 'timeline', label: 'Activity Log', icon: ActivityIcon, roles: [] },
  { id: 'verify', label: 'Public Verify', icon: QrCodeIcon, roles: [] },
  { id: 'settings', label: 'Settings', icon: SettingsIcon, roles: [] },
  { id: 'audit', label: 'Admin View', icon: UserIcon, roles: ['admin'] },
]

function readVerifyTokenFromUrl(): string | null {
  const m = window.location.hash.match(/#\/verify(?:-result)?\?token=([^&]+)/)
  return m ? decodeURIComponent(m[1]) : null
}

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-rose-600 shadow-lg shadow-brand-600/20 text-white">
        <ShieldIcon className="h-6 w-6" />
      </div>
      <div className="min-w-0">
        <p className="text-base font-extrabold tracking-tight text-slate-900">TRUSTVAULT</p>
        <p className="truncate text-[10px] text-slate-500 font-medium">Verify once. Control access everywhere.</p>
      </div>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState<CurrentUser | null>(getCurrentUser())
  const [tab, setTab] = useState<Tab>('dashboard')
  const [verifyToken, setVerifyToken] = useState<string | null>(null)

  useEffect(() => {
    const t = readVerifyTokenFromUrl()
    if (t) {
      setVerifyToken(t)
      setTab('verify')
    }
  }, [])

  if (!user) return <Login onLogin={setUser} />

  const visibleNav = NAV.filter((t) => t.roles.length === 0 || t.roles.includes(user.role))

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      /* best effort — still sign out locally */
    }
    setAuth(null)
    setUser(null)
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Desktop Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-ink-700 bg-white/90 backdrop-blur-xl lg:flex pt-10">
        <div className="px-6 py-4">
          <Brand />
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">Navigation</p>
          {visibleNav.map((t) => {
            const isActive = tab === t.id
            const Icon = t.icon
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  'group flex w-full items-center gap-3 rounded-2xl px-3.5 py-2.5 text-xs font-bold transition',
                  isActive
                    ? 'bg-gradient-to-r from-brand-50 to-rose-50 text-brand-700 ring-1 ring-brand-200'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                )}
              >
                <Icon
                  className={cn(
                    'h-4 w-4 shrink-0 transition',
                    isActive ? 'text-brand-600' : 'text-slate-400 group-hover:text-slate-600',
                  )}
                />
                <span className="flex-1 text-left">{t.label}</span>
                {isActive && (
                  <span className="h-1.5 w-1.5 rounded-full bg-brand-500 shadow-[0_0_10px] shadow-brand-500/60" />
                )}
              </button>
            )
          })}
        </nav>

        {/* User Account Info Footer */}
        <div className="border-t border-ink-700 p-4">
          <div className="flex items-center gap-3 rounded-2xl border border-ink-700 bg-white p-3 shadow-sm">
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-500 to-rose-600 text-xs font-bold text-white shadow-sm">
              {(user.full_name || user.email || '?').slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-bold text-slate-800">{user.full_name || user.email}</p>
              <p className="text-[10px] text-slate-500 capitalize font-medium">{user.role} mode</p>
            </div>
            <button
              onClick={logout}
              title="Sign Out"
              className="grid h-8 w-8 shrink-0 place-items-center rounded-xl border border-slate-200 text-slate-400 hover:border-rose-400 hover:bg-rose-50 hover:text-rose-600 transition"
            >
              <LogOutIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="lg:pl-64">
        {/* Mobile Header */}
        <header className="sticky top-0 z-30 border-b border-ink-700 bg-white/90 backdrop-blur lg:hidden px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <Brand />
            <button onClick={logout} className="text-xs font-semibold text-rose-600">
              Sign Out
            </button>
          </div>
          <nav className="flex gap-1 overflow-x-auto pt-3">
            {visibleNav.map((t) => {
              const isActive = tab === t.id
              const Icon = t.icon
              return (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={cn(
                    'flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold transition',
                    isActive ? 'bg-brand-50 text-brand-700 ring-1 ring-brand-300' : 'text-slate-600 hover:text-slate-900',
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {t.label}
                </button>
              )
            })}
          </nav>
        </header>

        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-10">
          <div key={tab} className="animate-fade-up">
            {tab === 'dashboard' && <DashboardPanel />}
            {tab === 'credentials' && <CredentialsPanel />}
            {tab === 'access' && <AccessPanel />}
            {tab === 'trust' && <TrustPanel user={user} />}
            {tab === 'timeline' && <TimelinePanel />}
            {tab === 'verify' && <VerifyPanel initialToken={verifyToken} />}
            {tab === 'settings' && <SettingsPanel user={user} />}
            {tab === 'audit' && <AuditPanel user={user} />}
          </div>
        </main>
      </div>
    </div>
  )
}