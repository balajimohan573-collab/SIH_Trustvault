import { useEffect, useState } from 'react'
import { getCurrentUser, credentialsApi, type Credential, type QrGenerate } from '../api'
import { Badge, EmptyState, BtnDanger, BtnPrimary, BtnGhost, Notice, decisionTone } from './ui'
import { BadgeCheckIcon, ChevronDownIcon, QrCodeIcon, ShieldIcon, PlusIcon, ShareIcon, EyeIcon } from './icons'
import AddCredentialWizard from './AddCredentialWizard'
import ShareCredentialModal from './ShareCredentialModal'

export default function CredentialsPanel() {
  const user = getCurrentUser()
  const isIssuerOrAdmin = user?.role === 'issuer' || user?.role === 'admin'
  const [creds, setCreds] = useState<Credential[]>([])
  const [msg, setMsg] = useState<{ tone: 'green' | 'red'; text: string } | null>(null)
  const [openWizard, setOpenWizard] = useState(false)
  const [shareCred, setShareCred] = useState<Credential | null>(null)
  const [qr, setQr] = useState<QrGenerate | null>(null)
  const [viewCred, setViewCred] = useState<Credential | null>(null)
  const [expandedTechId, setExpandedTechId] = useState<string | null>(null)

  const notify = (text: string, tone: 'green' | 'red' = 'green') => {
    setMsg({ tone, text })
  }

  async function refresh() {
    try {
      setCreds(await credentialsApi.list())
    } catch (e: any) {
      notify(e.message || 'Failed to load credentials.', 'red')
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function makeQr(c: Credential) {
    try {
      setQr(await credentialsApi.generateQr(c.id, 'verification', 5))
    } catch (e: any) {
      notify(e.message || 'QR generation failed.', 'red')
    }
  }

  async function revoke(id: string) {
    if (!confirm('Revoke this credential? Verification checks will immediately report it as revoked.')) return
    try {
      await credentialsApi.revoke(id, 'Revoked from the credential wallet')
      notify('Credential revoked — public verification now reports Revoked.')
      await refresh()
    } catch (e: any) {
      notify(e.message || 'Failed to revoke credential.', 'red')
    }
  }

  async function suspend(c: Credential) {
    try {
      await credentialsApi.suspend(c.id, 'Temporarily suspended from the wallet')
      notify('Credential suspended.')
      await refresh()
    } catch (e: any) {
      notify(e.message || 'Failed to suspend credential.', 'red')
    }
  }

  async function resume(c: Credential) {
    try {
      await credentialsApi.resume(c.id)
      notify('Credential reactivated.')
      await refresh()
    } catch (e: any) {
      notify(e.message || 'Failed to reactivate credential.', 'red')
    }
  }

  const statusTone = (s: string) => (s === 'active' ? 'green' : s === 'suspended' ? 'amber' : 'red')

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900">My Credentials</h2>
          <p className="text-xs text-slate-500">
            {isIssuerOrAdmin
              ? 'Credentials you hold and credentials your organization issued'
              : 'Your verified digital certificates and credentials'}
          </p>
        </div>
        {isIssuerOrAdmin && (
          <BtnPrimary onClick={() => setOpenWizard(true)} className="gap-2">
            <PlusIcon className="h-4 w-4" />
            Issue Credential
          </BtnPrimary>
        )}
      </div>

      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}

      {creds.length === 0 ? (
        <EmptyState
          icon={<ShieldIcon className="h-6 w-6" />}
          title="No credentials yet"
          hint={
            isIssuerOrAdmin
              ? 'Use “Issue Credential” to issue a verifiable credential to a holder.'
              : 'Credentials issued to you by a verified issuer will appear here.'
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {creds.map((c) => {
            const isRevoked = c.status === 'revoked'
            const isSuspended = c.status === 'suspended'
            const isTechOpen = expandedTechId === c.id
            const issuedByMe = c.issuer_user_id === user?.id
            return (
              <div
                key={c.id}
                className="group relative flex flex-col justify-between rounded-3xl border border-ink-700 bg-white p-5 shadow-sm transition hover:shadow-md"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600 border border-brand-100">
                      <BadgeCheckIcon className="h-6 w-6" />
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 justify-end">
                      {issuedByMe && <Badge tone="brand">issued</Badge>}
                      <Badge tone={statusTone(c.status)} dot>
                        {c.status}
                      </Badge>
                    </div>
                  </div>

                  <h3 className="mt-4 text-base font-bold leading-snug text-slate-900">{c.title ?? c.type}</h3>

                  <div className="mt-2 space-y-1 text-xs text-slate-500">
                    <p>
                      <span className="font-medium text-slate-700">Type:</span> {c.type}
                    </p>
                    <p>
                      <span className="font-medium text-slate-700">Issuer:</span> {c.issuer_name ?? '—'}
                    </p>
                    <p>
                      <span className="font-medium text-slate-700">Issued:</span>{' '}
                      {new Date(c.issued_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                    </p>
                    <p>
                      <span className="font-medium text-slate-700">Claims:</span> {c.claims.length}{' '}
                      {c.claims.length === 1 ? 'field' : 'fields'}
                    </p>
                  </div>
                </div>

                {/* Main Card Actions */}
                <div className="mt-5 pt-4 border-t border-slate-100 space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <BtnGhost
                      className="justify-center text-xs gap-1.5"
                      onClick={() => setViewCred(c)}
                    >
                      <EyeIcon className="h-3.5 w-3.5" />
                      View
                    </BtnGhost>

                    <BtnGhost
                      disabled={isRevoked || isSuspended}
                      className="justify-center text-xs gap-1.5"
                      onClick={() => setShareCred(c)}
                    >
                      <ShareIcon className="h-3.5 w-3.5" />
                      Share
                    </BtnGhost>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <BtnGhost
                      disabled={isRevoked || isSuspended}
                      className="justify-center text-xs gap-1.5"
                      onClick={() => makeQr(c)}
                    >
                      <QrCodeIcon className="h-3.5 w-3.5" />
                      QR Code
                    </BtnGhost>

                    <BtnDanger className="justify-center text-xs" disabled={isRevoked} onClick={() => revoke(c.id)}>
                      {isRevoked ? 'Revoked' : 'Revoke'}
                    </BtnDanger>
                  </div>

                  {issuedByMe && !isRevoked && (
                    <div className="grid grid-cols-1 gap-2">
                      {isSuspended ? (
                        <BtnGhost className="justify-center text-xs" onClick={() => resume(c)}>
                          Resume issuance
                        </BtnGhost>
                      ) : (
                        <BtnGhost className="justify-center text-xs text-amber-700 border-amber-200 bg-amber-50" onClick={() => suspend(c)}>
                          Suspend
                        </BtnGhost>
                      )}
                    </div>
                  )}

                  {/* Technical Details Accordion */}
                  <div className="pt-2">
                    <button
                      onClick={() => setExpandedTechId(isTechOpen ? null : c.id)}
                      className="flex w-full items-center justify-between text-[11px] font-medium text-slate-400 hover:text-slate-600"
                    >
                      <span>Technical Details</span>
                      <ChevronDownIcon className={`h-3.5 w-3.5 transition-transform ${isTechOpen ? 'rotate-180' : ''}`} />
                    </button>

                    {isTechOpen && (
                      <div className="mt-2 space-y-1.5 rounded-xl border border-slate-200 bg-slate-50 p-3 text-[10px] font-mono text-slate-600 animate-fade-up">
                        <p className="truncate">
                          <span className="font-semibold text-slate-800 font-sans">Claims hash:</span> {c.claims_hash}
                        </p>
                        {c.hash && (
                          <p className="truncate">
                            <span className="font-semibold text-slate-800 font-sans">Hash:</span> {c.hash}
                          </p>
                        )}
                        <p className="truncate">
                          <span className="font-semibold text-slate-800 font-sans">Anchor:</span>{' '}
                          {c.anchor_tx_hash ? `${c.anchor_tx_hash.slice(0, 18)}…` : 'pending'}
                        </p>
                        {c.external_id && (
                          <p className="truncate">
                            <span className="font-semibold text-slate-800 font-sans">External ID:</span> {c.external_id}
                          </p>
                        )}
                        <p className="truncate">
                          <span className="font-semibold text-slate-800 font-sans">Holder:</span> {c.holder_id}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <AddCredentialWizard
        isOpen={openWizard}
        onClose={() => setOpenWizard(false)}
        onSuccess={() => {
          refresh()
          notify('Credential issued — it now appears in the list.')
        }}
      />

      <ShareCredentialModal cred={shareCred} onClose={() => setShareCred(null)} />

      {/* QR Modal — rendered from a real backend token */}
      {qr && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-sm rounded-3xl border border-ink-700 bg-white p-6 shadow-2xl text-center space-y-4">
            <h3 className="text-base font-bold text-slate-900">Verifiable QR Code</h3>
            <p className="text-xs text-slate-500">Scan to verify this credential instantly — expires {new Date(qr.expires_at).toLocaleTimeString()}</p>

            <img
              src={`/api${verifyImage(qr.qr_token)}`}
              alt="Credential QR"
              className="mx-auto h-48 w-48 rounded-2xl border border-slate-200 bg-white p-3 shadow-inner"
            />

            <p className="text-[11px] text-slate-500 break-all font-mono bg-slate-50 p-2 rounded-xl">{qr.qr_url}</p>

            <div className="grid grid-cols-2 gap-2">
              <BtnGhost
                className="justify-center text-xs"
                onClick={() => {
                  navigator.clipboard?.writeText(window.location.origin + qr.qr_url)
                  notify('Verification link copied.')
                  setQr(null)
                }}
              >
                Copy link
              </BtnGhost>
              <BtnPrimary className="justify-center text-xs" onClick={() => setQr(null)}>
                Done
              </BtnPrimary>
            </div>
          </div>
        </div>
      )}

      {/* View Credential Detail Modal */}
      {viewCred && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-md rounded-3xl border border-ink-700 bg-white p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center gap-3">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-600">
                <BadgeCheckIcon className="h-7 w-7" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">{viewCred.title ?? viewCred.type}</h3>
                <Badge tone={decisionTone(viewCred.status === 'active' ? 'ALLOW' : 'DENY')} dot className="mt-1">
                  {viewCred.status}
                </Badge>
              </div>
            </div>

            <div className="space-y-2 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs">
              <p><b className="text-slate-800">Type:</b> {viewCred.type}</p>
              <p><b className="text-slate-800">Issuer:</b> {viewCred.issuer_name ?? viewCred.issuer_org_id}</p>
              <p><b className="text-slate-800">Holder:</b> {viewCred.holder_id}</p>
              <p><b className="text-slate-800">Issued:</b> {new Date(viewCred.issued_at).toLocaleString()}</p>
              {viewCred.expiry_date && <p><b className="text-slate-800">Expires:</b> {viewCred.expiry_date}</p>}
              {viewCred.external_id && <p><b className="text-slate-800">External ID:</b> {viewCred.external_id}</p>}
            </div>

            {viewCred.claims.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-bold text-slate-800">Structured claims</p>
                <div className="grid grid-cols-1 gap-2">
                  {viewCred.claims.map((cl) => (
                    <div key={cl.key} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs">
                      <span className="font-medium text-slate-600">{cl.key.replace(/_/g, ' ')}</span>
                      <span className="max-w-[55%] truncate font-bold text-slate-900">{cl.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {viewCred.files.length > 0 && (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs">
                <p className="font-bold text-slate-800 mb-1.5">Evidence files</p>
                {viewCred.files.map((f) => (
                  <p key={f.id} className="truncate font-mono text-[11px] text-slate-500">
                    {f.original_filename} · {f.sha256.slice(0, 18)}…
                  </p>
                ))}
              </div>
            )}

            <BtnPrimary className="w-full justify-center" onClick={() => setViewCred(null)}>
              Close
            </BtnPrimary>
          </div>
        </div>
      )}
    </div>
  )
}

function verifyImage(qrToken: string) {
  return `/verify/${encodeURIComponent(qrToken)}/qr`
}