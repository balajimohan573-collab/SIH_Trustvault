import { useEffect, useRef, useState } from 'react'
import { useLang, tr, speak } from '../i18n'
import { ShieldIcon } from './icons'
import { SpeakerButton } from './ui'

const VISITED_KEY = 'trustvault.onboarded'

export default function Walkthrough() {
  const lang = useLang()
  const [open, setOpen] = useState(false)
  const script = tr(lang, 'onboard_script')
  const spokeLang = useRef<string | null>(null)

  useEffect(() => {
    let visited = true
    try {
      visited = localStorage.getItem(VISITED_KEY) === '1'
    } catch {
      /* private mode — always show */
    }
    if (!visited) setOpen(true)
  }, [])

  useEffect(() => {
    if (!open) return
    if (spokeLang.current === lang) return
    spokeLang.current = lang
    const id = setTimeout(() => speak(script, lang), 350)
    return () => clearTimeout(id)
  }, [open, lang, script])

  function dismiss() {
    try {
      localStorage.setItem(VISITED_KEY, '1')
    } catch {
      /* ignore */
    }
    setOpen(false)
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center p-4 sm:items-center">
      <button aria-label="close" onClick={dismiss} className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" />
      <div className="relative w-full max-w-md animate-fade-up rounded-3xl border border-ink-700 bg-white p-6 shadow-2xl">
        <div className="pointer-events-none absolute -top-10 right-4 h-24 w-24 rounded-full bg-brand-500/20 blur-2xl" />

        <div className="flex items-center gap-3">
          <div className="relative grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-rose-600 shadow-lg shadow-brand-600/25">
            <ShieldIcon className="h-6 w-6 text-white" />
          </div>
          <div className="min-w-0">
            <h2 className="text-base font-bold tracking-tight text-slate-900">{tr(lang, 'onboard_title')}</h2>
            <p className="text-xs text-slate-500">{tr(lang, 'onboard_sub')}</p>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-brand-100 bg-brand-50/60 p-4">
          <p className="text-sm leading-relaxed text-slate-700">{script}</p>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <SpeakerButton text={script} tone="brand" />
          <span className="text-[11px] text-slate-400">{tr(lang, 'onboard_replay')}</span>
        </div>

        <button
          onClick={dismiss}
          className="mt-4 w-full rounded-2xl bg-gradient-to-r from-brand-500 to-rose-600 px-4 py-3.5 text-sm font-bold text-white shadow-lg shadow-brand-600/25 transition hover:brightness-105 active:scale-[0.98]"
        >
          {tr(lang, 'onboard_start')}
        </button>
      </div>
    </div>
  )
}