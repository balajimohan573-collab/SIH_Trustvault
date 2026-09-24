import { useEffect, useState } from 'react'
import { LANGS, getStoredLang, storeLang, type Lang } from '../i18n'
import { cn } from './ui'

export default function LanguageSwitcher({ className }: { className?: string }) {
  const [lang, setLang] = useState<Lang>(getStoredLang())

  useEffect(() => {
    document.documentElement.lang = lang
    storeLang(lang)
  }, [lang])

  return (
    <div
      className={cn(
        'flex items-center gap-1 rounded-xl border border-ink-700 bg-white p-1 shadow-sm',
        className,
      )}
      role="group"
      aria-label="Choose language"
    >
      {LANGS.map((l) => (
        <button
          key={l.id}
          onClick={() => setLang(l.id)}
          title={l.label}
          className={cn(
            'min-w-[44px] rounded-lg px-2.5 py-1.5 text-xs font-semibold transition',
            lang === l.id
              ? 'bg-gradient-to-r from-brand-500 to-rose-600 text-white shadow-sm'
              : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800',
          )}
        >
          {l.short}
        </button>
      ))}
    </div>
  )
}