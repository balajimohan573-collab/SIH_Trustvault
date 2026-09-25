import { useState } from 'react'
import { BadgeCheckIcon, CheckIcon, XIcon } from './icons'
import { BtnGhost, BtnPrimary, Field, Input, Notice, Spinner } from './ui'
import { credentialsApi, getCurrentUser, type Credential } from '../api'

type ClaimRow = { key: string; value: string; public: boolean }

export default function AddCredentialWizard({
  isOpen,
  onClose,
  onSuccess,
}: {
  isOpen: boolean
  onClose: () => void
  onSuccess: (c: Credential) => void
}) {
  const user = getCurrentUser()
  const [step, setStep] = useState<'form' | 'done'>('form')
  const [holderEmail, setHolderEmail] = useState('')
  const [type, setType] = useState('')
  const [title, setTitle] = useState('')
  const [externalId, setExternalId] = useState('')
  const [issueDate, setIssueDate] = useState('')
  const [expiryDate, setExpiryDate] = useState('')
  const [claims, setClaims] = useState<ClaimRow[]>([{ key: '', value: '', public: true }])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<Credential | null>(null)

  if (!isOpen) return null
  if (user?.role !== 'issuer' && user?.role !== 'admin') {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
        <div className="relative w-full max-w-md rounded-3xl border border-ink-700 bg-white p-6 shadow-2xl">
          <button onClick={onClose} className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-full text-slate-400 hover:bg-slate-100">
            <XIcon className="h-5 w-5" />
          </button>
          <h2 className="text-lg font-bold text-slate-900">Only issuers can issue credentials</h2>
          <p className="mt-2 text-xs text-slate-500 leading-relaxed">
            Credentials are issued by verified organizations. If you represent an organization, sign in as its issuer and apply
            for verification — once approved you can issue credentials here.
          </p>
          <BtnPrimary className="mt-5 w-full justify-center" onClick={onClose}>
            Close
          </BtnPrimary>
        </div>
      </div>
    )
  }

  function updateClaim(i: number, patch: Partial<ClaimRow>) {
    setClaims((prev) => prev.map((c, idx) => (idx === i ? { ...c, ...patch } : c)))
  }

  const addClaimRow = () => setClaims((prev) => [...prev, { key: '', value: '', public: true }])
  const removeClaimRow = (i: number) => setClaims((prev) => prev.filter((_, idx) => idx !== i))

  async function handleIssue() {
    setBusy(true)
    setError(null)
    try {
      const cleanClaims = claims
        .filter((c) => c.key.trim() && c.value.trim())
        .map((c) => ({ key: c.key.trim(), value: c.value.trim(), public: c.public }))
      if (!type.trim()) throw new Error('Credential type is required.')
      const c = await credentialsApi.issue({
        holder_email: holderEmail.trim() || undefined,
        type: type.trim(),
        title: title.trim() || undefined,
        external_id: externalId.trim() || undefined,
        issue_date: issueDate || undefined,
        expiry_date: expiryDate || undefined,
        claims: cleanClaims,
      })
      setCreated(c)
      setStep('done')
    } catch (e: any) {
      setError(e.message || 'Issuance failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-lg rounded-3xl border border-ink-700 bg-white p-6 shadow-2xl animate-fade-up max-h-[92vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <XIcon className="h-5 w-5" />
        </button>

        {step === 'form' ? (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Issue Credential</h2>
            <p className="text-xs text-slate-500">
              You are issuing as <b className="text-slate-700">{user.email}</b>. The credential is anchored to your verified organization.
            </p>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Credential type" hint="required">
                <Input value={type} onChange={(e) => setType(e.target.value)} placeholder="e.g. Degree Certificate" />
              </Field>
              <Field label="Title">
                <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Bachelor of Engineering" />
              </Field>
            </div>

            <Field label="Holder email" hint="leave blank to issue to yourself">
              <Input type="email" value={holderEmail} onChange={(e) => setHolderEmail(e.target.value)} placeholder="holder@example.com" />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Issue date">
                <Input type="date" value={issueDate} onChange={(e) => setIssueDate(e.target.value)} />
              </Field>
              <Field label="Expiry date">
                <Input type="date" value={expiryDate} onChange={(e) => setExpiryDate(e.target.value)} />
              </Field>
            </div>

            <Field label="External ID">
              <Input value={externalId} onChange={(e) => setExternalId(e.target.value)} placeholder="e.g. roll number" />
            </Field>

            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <p className="text-xs font-medium text-slate-600">Structured claims</p>
                <button type="button" onClick={addClaimRow} className="text-xs font-bold text-brand-600 hover:text-brand-700">
                  + Add claim
                </button>
              </div>
              <div className="space-y-2">
                {claims.map((cl, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input
                      value={cl.key}
                      onChange={(e) => updateClaim(i, { key: e.target.value })}
                      placeholder="field name (e.g. full_name)"
                      className="!w-1/3 font-mono text-xs"
                    />
                    <Input
                      value={cl.value}
                      onChange={(e) => updateClaim(i, { value: e.target.value })}
                      placeholder="value"
                      className="flex-1 text-xs"
                    />
                    <label className="flex items-center gap-1 text-[10px] font-semibold text-slate-500 shrink-0">
                      <input
                        type="checkbox"
                        checked={cl.public}
                        onChange={(e) => updateClaim(i, { public: e.target.checked })}
                        className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                      />
                      public
                    </label>
                    <button
                      type="button"
                      onClick={() => removeClaimRow(i)}
                      className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-slate-200 text-slate-400 hover:text-rose-600 hover:border-rose-300"
                    >
                      <XIcon className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
              <p className="mt-1 text-[10px] text-slate-400">Public claims are disclosed in QR verification; private claims stay with the holder.</p>
            </div>

            {error && <Notice tone="red">{error}</Notice>}

            <div className="flex justify-between items-center pt-2">
              <BtnGhost onClick={onClose}>Cancel</BtnGhost>
              <BtnPrimary onClick={handleIssue} disabled={busy}>
                {busy && <Spinner />}
                {busy ? 'Issuing…' : 'Issue verifiable credential'}
              </BtnPrimary>
            </div>
          </div>
        ) : (
          <div className="py-4 text-center space-y-4">
            <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-emerald-100 text-emerald-600 shadow-lg">
              <BadgeCheckIcon className="h-9 w-9" />
            </div>

            <div>
              <h3 className="text-lg font-bold text-slate-900">Credential Issued</h3>
              <p className="text-xs text-slate-500 mt-1">
                {created?.title ?? created?.type} · holder {created?.holder_id?.slice(0, 8)}…
              </p>
            </div>

            <div className="mx-auto max-w-xs space-y-2.5 rounded-2xl border border-emerald-100 bg-emerald-50/60 p-4 text-left text-xs font-medium text-emerald-800">
              <div className="flex items-center gap-2">
                <CheckIcon className="h-4 w-4 text-emerald-600 shrink-0" />
                <span>Claims hashed and recorded</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckIcon className="h-4 w-4 text-emerald-600 shrink-0" />
                <span>Verification token generated</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckIcon className="h-4 w-4 text-emerald-600 shrink-0" />
                <span>Anchor pending (winner chain: queued)</span>
              </div>
            </div>

            <div className="pt-2">
              <BtnPrimary
                className="w-full"
                onClick={() => {
                  if (created) onSuccess(created)
                  setStep('form')
                  setCreated(null)
                  onClose()
                }}
              >
                View credentials
              </BtnPrimary>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}