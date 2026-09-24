import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { dashboardApi, duressApi, type DashboardSummary } from '../api'
import { Badge, Panel, cn } from './ui'
import { ShieldIcon, QrCodeIcon, FolderLockIcon, KeyIcon, UploadIcon, BadgeCheckIcon, ActivityIcon } from './icons'
import { useLang, tr } from '../i18n'

type Tab = 'dashboard' | 'verify' | 'trust' | 'timeline' | 'credentials' | 'assets' | 'access' | 'audit'

function ActionCard({
  icon,
  title,
  hint,
  accent,
  onClick,
}: {
  icon: ReactNode
  title: string
  hint: string
  accent: string
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="group flex flex-col items-start gap-3 rounded-2xl border border-ink-700 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg"
    >
      <div className={cn('grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br text-white shadow-lg', accent)}>
        {icon}
      </div>
      <div>
        <p className="text-sm font-bold text-slate-900">{title}</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-500">{hint}</p>
      </div>
    </button>
  )
}

export default function HomePanel({ onNavigate }: { onNavigate: (t: Tab) => void }) {
  const [sum, setSum] = useState<DashboardSummary | null>(null)
  const [duress, setDuress] = useState<{ active: boolean } | null>(null)
  const lang = useLang()

  async function load() {
    try {
      setSum(await dashboardApi.summary(false))
    } catch {
      /* offline */
    }
    try {
      const d = await duressApi.status()
      setDuress(d)
    } catch {
      /* offline */
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [])

  const score = sum?.trust?.current_score ?? null
  const scoreTone = score === null ? 'slate' : score >= 70 ? 'green' : score >= 40 ? 'amber' : 'red'
  const certs = (sum?.user_role === 'admin' ? sum?.credentials?.issued_total : sum?.credentials?.held_total) ?? 0
  const docs = sum?.assets?.owned_total ?? 0
  const pending = (sum?.pending_requests ?? []).length

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-ink-700 bg-gradient-to-r from-brand-50 via-rose-50 to-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-slate-900">{tr(lang, 'home_welcome')}</h2>
            <p className="mt-1 max-w-lg text-sm leading-relaxed text-slate-600">{tr(lang, 'home_sub')}</p>
          </div>
          <div className="relative grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-rose-600 shadow-xl shadow-brand-600/25">
            <ShieldIcon className="h-9 w-9 text-white" />
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="flex items-center gap-3 rounded-xl border border-ink-700 bg-white p-4">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-brand-100 bg-brand-50 text-brand-600">
              <ShieldIcon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-slate-500">{tr(lang, 'home_security')}</p>
              <p className="text-lg font-bold text-slate-900">{score === null ? '—' : `${score}/100`}</p>
            </div>
            <Badge tone={scoreTone} dot className="ml-auto">
              {score === null ? '‑' : score >= 70 ? 'OK' : score >= 40 ? 'careful' : 'risk'}
            </Badge>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-ink-700 bg-white p-4">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-brand-100 bg-brand-50 text-brand-600">
              <BadgeCheckIcon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-slate-500">{tr(lang, 'home_certs')}</p>
              <p className="text-lg font-bold text-slate-900">{certs}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-ink-700 bg-white p-4">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-brand-100 bg-brand-50 text-brand-600">
              <FolderLockIcon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-slate-500">{tr(lang, 'home_docs')}</p>
              <p className="text-lg font-bold text-slate-900">{docs}</p>
            </div>
          </div>
        </div>
      </div>

      <div>
        <p className="mb-3 text-sm font-bold text-slate-800">{tr(lang, 'home_quick')}</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <ActionCard
            icon={<BadgeCheckIcon className="h-5 w-5" />}
            title={tr(lang, 'act_add_cert')}
            hint={tr(lang, 'act_add_cert_hint')}
            accent="from-brand-500 to-sky-600"
            onClick={() => onNavigate('credentials')}
          />
          <ActionCard
            icon={<UploadIcon className="h-5 w-5" />}
            title={tr(lang, 'act_store_doc')}
            hint={tr(lang, 'act_store_doc_hint')}
            accent="from-emerald-500 to-teal-600"
            onClick={() => onNavigate('assets')}
          />
          <ActionCard
            icon={<QrCodeIcon className="h-5 w-5" />}
            title={tr(lang, 'act_share')}
            hint={tr(lang, 'act_share_hint')}
            accent="from-violet-500 to-fuchsia-600"
            onClick={() => onNavigate('credentials')}
          />
          <ActionCard
            icon={<ShieldIcon className="h-5 w-5" />}
            title={tr(lang, 'act_check')}
            hint={tr(lang, 'act_check_hint')}
            accent="from-rose-500 to-red-600"
            onClick={() => onNavigate('trust')}
          />
          <ActionCard
            icon={<KeyIcon className="h-5 w-5" />}
            title={tr(lang, 'act_requests')}
            hint={tr(lang, 'act_requests_hint')}
            accent="from-amber-500 to-orange-600"
            onClick={() => onNavigate('access')}
          />
          <ActionCard
            icon={<ActivityIcon className="h-5 w-5" />}
            title={tr(lang, 'home_activity')}
            hint={tr(lang, 'nav_timeline') + ' · ' + tr(lang, 'nav_audit')}
            accent="from-slate-600 to-slate-800"
            onClick={() => onNavigate('timeline')}
          />
        </div>
      </div>

      <Panel title={tr(lang, 'home_requests')} icon={<KeyIcon className="h-5 w-5" />}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-600">
            <b className="text-slate-900">{pending}</b> {tr(lang, 'pending_unit')}
          </p>
          {pending > 0 && (
            <button
              onClick={() => onNavigate('access')}
              className="rounded-xl bg-gradient-to-r from-brand-500 to-rose-600 px-4 py-2 text-sm font-bold text-white shadow-lg shadow-brand-600/25 transition hover:brightness-105 active:scale-95"
            >
              {tr(lang, 'act_requests')}
            </button>
          )}
        </div>
      </Panel>

      {duress?.active && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-rose-200 bg-white text-rose-600">
              <ShieldIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-bold text-rose-800">{tr(lang, 'home_security')}</p>
              <p className="text-xs text-rose-700">{tr(lang, 'r_DURESS_ACTIVE')}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}