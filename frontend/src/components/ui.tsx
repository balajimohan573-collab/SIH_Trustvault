import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'
import { AlertIcon, CheckIcon, InfoIcon, XIcon } from './icons'

export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}

export type Tone = 'green' | 'amber' | 'red' | 'slate' | 'blue' | 'brand' | 'violet'

const badgeTones: Record<Tone, string> = {
  green: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  amber: 'border-amber-200 bg-amber-50 text-amber-700',
  red: 'border-rose-300 bg-rose-50 text-rose-700',
  blue: 'border-sky-200 bg-sky-50 text-sky-700',
  slate: 'border-slate-300 bg-slate-100 text-slate-600',
  brand: 'border-brand-200 bg-brand-50 text-brand-700',
  violet: 'border-violet-200 bg-violet-50 text-violet-700',
}

const dotTones: Record<Tone, string> = {
  green: 'bg-emerald-500',
  amber: 'bg-amber-500',
  red: 'bg-rose-500',
  blue: 'bg-sky-500',
  slate: 'bg-slate-500',
  brand: 'bg-brand-500',
  violet: 'bg-violet-500',
}

export function Badge({
  tone = 'slate',
  dot,
  children,
  className,
}: {
  tone?: Tone
  dot?: boolean
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium',
        badgeTones[tone],
        className,
      )}
    >
      {dot && <span className={cn('h-1.5 w-1.5 rounded-full', dotTones[tone])} />}
      {children}
    </span>
  )
}

export function decisionTone(d: string): 'green' | 'amber' | 'red' | 'violet' | 'slate' {
  if (d === 'ALLOW') return 'green'
  if (d === 'STEP_UP') return 'amber'
  if (d === 'RESTRICTED') return 'violet'
  if (d === 'DENY') return 'red'
  return 'slate'
}

const tipSides = {
  top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
  bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
  left: 'right-full top-1/2 -translate-y-1/2 mr-2',
  right: 'left-full top-1/2 -translate-y-1/2 ml-2',
} as const

export function Tip({
  label,
  side = 'bottom',
  children,
  className,
}: {
  label: string
  side?: keyof typeof tipSides
  children: ReactNode
  className?: string
}) {
  return (
    <span className={cn('group/tip relative inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        aria-label={label}
        title={label}
        className={cn(
          'pointer-events-none absolute z-50 w-max max-w-[260px] rounded-lg bg-slate-900 px-3 py-2 text-[11px] font-medium leading-snug text-white opacity-0 shadow-xl ring-1 ring-slate-900/10 transition duration-150',
          'group-hover/tip:opacity-100 group-focus-within/tip:opacity-100 group-active/tip:opacity-100',
          tipSides[side],
        )}
      >
        {label}
      </span>
    </span>
  )
}

export function Panel({
  title,
  subtitle,
  icon,
  actions,
  help,
  children,
  className,
}: {
  title: string
  subtitle?: string
  icon?: ReactNode
  actions?: ReactNode
  help?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('relative rounded-2xl border border-ink-700 bg-white p-5 shadow-sm shadow-slate-200/70', className)}>
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px rounded-t-2xl bg-gradient-to-r from-transparent via-slate-200 to-transparent" />
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {icon && (
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-brand-100 bg-brand-50 text-brand-600">
              {icon}
            </div>
          )}
          <div>
            <div className="flex items-center gap-1.5">
              <h2 className="text-sm font-semibold tracking-wide text-slate-800">{title}</h2>
              {help && (
                <Tip label={help} side="bottom">
                  <span
                    tabIndex={0}
                    className="grid h-4.5 w-4.5 h-5 w-5 cursor-help place-items-center rounded-full border border-ink-600 bg-white text-[11px] font-bold text-slate-500 transition hover:border-brand-400 hover:text-brand-600"
                  >
                    ?
                  </span>
                </Tip>
              )}
            </div>
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          </div>
        </div>
        {actions}
      </div>
      <div className="mt-5">{children}</div>
    </section>
  )
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-baseline justify-between gap-2 text-xs font-medium text-slate-600">
        <span>{label}</span>
        {hint && <span className="font-normal text-slate-400">{hint}</span>}
      </span>
      {children}
    </label>
  )
}

export const inputCls =
  'w-full rounded-lg border border-ink-600 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-500/15'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(inputCls, className)} {...props} />
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(inputCls, 'appearance-none cursor-pointer pr-8', className)} {...props} />
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(inputCls, 'resize-y', className)} {...props} />
}

const btnBase =
  'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:cursor-not-allowed'

export function BtnPrimary({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        btnBase,
        'bg-gradient-to-b from-brand-500 to-brand-600 text-white shadow-lg shadow-brand-600/25 hover:from-brand-400 hover:to-brand-500 disabled:opacity-50 disabled:shadow-none',
        className,
      )}
      {...props}
    />
  )
}

export function BtnGhost({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        btnBase,
        'border border-ink-600 bg-white text-slate-700 hover:border-brand-400 hover:bg-brand-50 hover:text-brand-600 disabled:opacity-50 disabled:hover:border-ink-600 disabled:hover:bg-white disabled:hover:text-slate-700',
        className,
      )}
      {...props}
    />
  )
}

export function BtnDanger({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        btnBase,
        'border border-rose-300 bg-rose-50 text-rose-700 hover:border-rose-400 hover:bg-rose-100 disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={cn('h-4 w-4 animate-spin text-current', className)}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.3" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

const noticeTones = {
  green: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  amber: 'border-amber-200 bg-amber-50 text-amber-800',
  red: 'border-rose-200 bg-rose-50 text-rose-800',
  slate: 'border-ink-600 bg-slate-50 text-slate-600',
}

const noticeIcons = {
  green: CheckIcon,
  amber: AlertIcon,
  red: XIcon,
  slate: InfoIcon,
}

export function Notice({
  tone = 'slate',
  children,
  className,
}: {
  tone?: keyof typeof noticeTones
  children: ReactNode
  className?: string
}) {
  const Icon = noticeIcons[tone]
  return (
    <div className={cn('flex items-start gap-2.5 rounded-xl border px-3.5 py-2.5 text-xs', noticeTones[tone], className)}>
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <div className="min-w-0 break-words leading-relaxed">{children}</div>
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-ink-600 bg-white/70 px-6 py-10 text-center">
      {icon && (
        <div className="mb-3 grid h-12 w-12 place-items-center rounded-2xl border border-ink-700 bg-slate-100 text-slate-400">
          {icon}
        </div>
      )}
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-xs leading-relaxed text-slate-500">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}