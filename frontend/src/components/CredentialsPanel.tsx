import { useEffect, useState } from 'react'
import { api, qrApi, type Credential } from '../api'
import { Badge, EmptyState, Field, Notice, Panel, BtnDanger, BtnPrimary, BtnGhost, Input, Textarea } from './ui'
import { BadgeCheckIcon, CodeIcon, QrCodeIcon, ShieldIcon } from './icons'

export default function CredentialsPanel({ userRole }: { userRole: string }) {
  const [creds, setCreds] = useState<Credential[]>([])
  const [holderEmail, setHolderEmail] = useState('holder@trustvault.example')
  const [type, setType] = useState('education_certificate')
  const [claim, setClaim] = useState('{"degree":"B.Sc.","university":"IIT, Mumbai"}')
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const isIssuer = userRole === 'issuer' || userRole === 'admin'

  async function refresh() {
    setCreds(await api.get<Credential[]>('/credentials?holder=me'))
  }

  const [qrUrl, setQrUrl] = useState<string | null>(null)

  async function makeQr(c: Credential) {
    try {
      const r = await qrApi.generate(c.id, 'verification', 5)
      setQrUrl(r.qr_url)
      setMsg(`QR token expires in 5 minutes. Scan with the Verify tab.`)
    } catch (e: any) {
      setErr(`QR failed: ${e.message ?? 'unknown error'}`)
    }
  }

  useEffect(() => {
    refresh().catch(() => setErr('Failed to load credentials'))
  }, [])

  async function issue() {
    setMsg(null)
    setErr(null)
    try {
      let document: Record<string, unknown>
      try {
        document = JSON.parse(claim)
      } catch {
        document = { freeform: claim }
      }
      await api.post('/credentials/issue', { holder_email: holderEmail, type, document })
      setMsg(`Credential issued to ${holderEmail}`)
      await refresh()
    } catch (e: any) {
      setErr(`Issue failed: ${e.message ?? 'unknown error'}`)
    }
  }

  async function revoke(id: string) {
    if (!confirm('Revoke this credential? It will fail all future verifications.')) return
    try {
      await api.post(`/credentials/${id}/revoke`, { reason: 'demo revoke' })
      setMsg('Credential revoked — verifications will now fail.')
    } catch {
      /* ignore */
    }
    await refresh()
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      {isIssuer && (
        <Panel
          title="Issue credential"
          subtitle="Issuer verifies identity and issues a hash-only credential"
          icon={<BadgeCheckIcon className="h-5 w-5" />}
        >
          <div className="space-y-3.5">
            <Field label="Holder email" hint="who receives the credential">
              <Input value={holderEmail} onChange={(e) => setHolderEmail(e.target.value)} placeholder="holder email" />
            </Field>
            <Field label="Credential type" hint="e.g. education_certificate">
              <Input value={type} onChange={(e) => setType(e.target.value)} placeholder="credential type" />
            </Field>
            <Field label="Claim document" hint="JSON — hashed, never stored raw">
              <Textarea rows={4} value={claim} onChange={(e) => setClaim(e.target.value)} className="font-mono text-xs" />
            </Field>
            <BtnPrimary className="w-full" onClick={issue}>
              Issue credential
            </BtnPrimary>
            {msg && (
              <Notice tone="green">
                {msg}
              </Notice>
            )}
            {err && (
              <Notice tone="red">
                {err}
              </Notice>
            )}
          </div>
        </Panel>
      )}

      <Panel
        title={isIssuer ? 'Issued credentials' : 'My credentials'}
        subtitle="Only SHA-256 hashes are stored — never the raw document"
        icon={<ShieldIcon className="h-5 w-5" />}
        className={isIssuer ? '' : 'lg:col-span-2'}
      >
        {creds.length === 0 ? (
          <EmptyState
            icon={<ShieldIcon className="h-5 w-5" />}
            title="No credentials yet"
            hint="Issued credentials appear here with their on-chain status hash, ready for verification."
          />
        ) : (
          <div className="space-y-3">
            {creds.map((c) => (
              <div
                key={c.id}
                className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300"
              >
                <div className="flex min-w-0 items-start gap-3">
                  <div className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-brand-100 bg-brand-50 text-brand-600">
                    <CodeIcon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-slate-800">{c.type}</span>
                      <Badge tone={c.status === 'active' ? 'green' : 'red'} dot>
                        {c.status}
                      </Badge>
                    </div>
                    <p className="mt-1.5 font-mono text-[10px] text-slate-500">issuer {c.issuer_id.slice(0, 12)}…</p>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 font-mono text-[10px] text-slate-500">
                      <span title={c.hash}>sha256 {c.hash.slice(0, 24)}…</span>
                      <span title={c.id}>id {c.id.slice(0, 10)}…</span>
                      <span>issued {new Date(c.issued_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {!isIssuer && c.status === 'active' && (
                    <BtnGhost className="!px-3 !py-1.5 text-xs" onClick={() => makeQr(c)}>
                      <QrCodeIcon className="h-3.5 w-3.5" />
                      QR
                    </BtnGhost>
                  )}
                  {isIssuer && c.status === 'active' && (
                    <BtnDanger className="!px-3 !py-1.5 text-xs" onClick={() => revoke(c.id)}>
                      Revoke
                    </BtnDanger>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        {qrUrl && (
          <Notice tone="slate" className="mt-3">
            <span className="flex flex-wrap items-center gap-2">
              <QrCodeIcon className="h-3.5 w-3.5 shrink-0" />
              Open the <b className="font-mono">{qrUrl}</b> link (or paste it into the Verify tab) to prove the
              credential. The token self-expires after 5 minutes.
              <button
                onClick={() => {
                  navigator.clipboard?.writeText(qrUrl)
                  setMsg('QR link copied to clipboard.')
                }}
                className="font-semibold text-brand-700 underline underline-offset-2 hover:text-brand-800"
              >
                copy
              </button>
            </span>
          </Notice>
        )}
        {!isIssuer && msg && <Notice tone="green" className="mt-3">{msg}</Notice>}
        {!isIssuer && err && <Notice tone="red" className="mt-3">{err}</Notice>}
      </Panel>
    </div>
  )
}