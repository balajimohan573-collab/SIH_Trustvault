import { useEffect, useRef, useState } from 'react'
import { api, getCurrentUser, type Asset } from '../api'
import { Badge, EmptyState, Field, Notice, Panel, BtnGhost, BtnPrimary, Input, Select, Spinner, cn, decisionTone, Tip, SpeakerButton } from './ui'
import { ArrowDownIcon, FileTextIcon, FolderLockIcon, LockIcon, UploadIcon, GiveIcon, ShieldAlertIcon } from './icons'
import { useLang, tr } from '../i18n'

function PipelineResult({ body }: { body: any }) {
  const d = body?.detail
  const lang = useLang()
  if (!d) return null
  const tone = decisionTone(d.decision ?? '')
  const banner = {
    green: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    amber: 'border-amber-200 bg-amber-50 text-amber-800',
    violet: 'border-violet-200 bg-violet-50 text-violet-800',
    red: 'border-rose-200 bg-rose-50 text-rose-800',
    slate: 'border-slate-300 bg-slate-50 text-slate-700',
  }[tone]
  const theory = tr(lang, `dec_${d.decision}`)
  const human = d.human ? tr(lang, `decHit_${d.decision}`) : undefined
  const reasonText = Array.isArray(d.reasons_human)
    ? d.reasons_human.map((r: any) => r.code).join(', ')
    : ''
  return (
    <div className={cn('mt-5 rounded-xl border p-4', banner)}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-widest text-current/70">Access pipeline</span>
        <Badge tone={tone}>{theory}</Badge>
        <span className="ml-auto font-mono text-xs opacity-70">trust {d.trust_score}</span>
      </div>
      {human && <p className="mt-2 text-xs font-medium">{human}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <SpeakerButton text={`${theory}. ${human ?? ''} ${reasonText}`} tone={tone} />
        {Array.isArray(d.reasons_human) && d.reasons_human.length > 0 && (
          <span className="text-[10px] opacity-60">{tr(lang, 'speak_button')}: reasons {reasonText}</span>
        )}
      </div>
      {d.scope && <p className="mt-1 text-[11px] opacity-80">Scope: {d.scope}</p>}
      {d.next_action && (
        <p className="mt-2 rounded-lg border border-current/10 bg-white/50 px-2.5 py-1.5 text-[11px]">
          Next action: <b>{d.next_action}</b>
        </p>
      )}
      {Array.isArray(d.reasons_human) && d.reasons_human.length > 0 && (
        <ul className="mt-2 space-y-1">
          {d.reasons_human.map((r: any) => (
            <li key={r.code} className="flex items-start gap-2 text-[11px]">
              <code className="rounded border border-current/15 bg-white/50 px-1 py-px font-mono">{r.code}</code>
              <span className="opacity-90">{tr(lang, `r_${r.code}`)}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 font-mono text-[10px] opacity-60">model {d.model_version}</p>
    </div>
  )
}

export default function AssetsPanel({ onPipeline }: { onPipeline: (r: any) => void }) {
  const user = getCurrentUser()
  const [assets, setAssets] = useState<Asset[]>([])
  const [users, setUsers] = useState<any[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [policy, setPolicy] = useState<{
    asset_id: string
    role: string
    purpose: string
    min_trust: string
    location_scope: string
    location_strict: boolean
    time_start: string
    time_end: string
  }>({
    asset_id: '',
    role: 'verifier',
    purpose: 'employment',
    min_trust: '50',
    location_scope: '',
    location_strict: false,
    time_start: '',
    time_end: '',
  })
  const [transfer, setTransfer] = useState<{ asset_id: string; to_user_id: string }>({
    asset_id: '',
    to_user_id: '',
  })
  const [msg, setMsg] = useState<NoticeState | null>(null)
  const [pipeline, setPipeline] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  async function refresh() {
    setAssets(await api.get<Asset[]>('/assets'))
    api.get<any[]>('/auth/users').then(setUsers).catch(() => {})
  }
  useEffect(() => {
    refresh().catch(() => {})
  }, [])

  async function upload() {
    if (!file) return
    setMsg(null)
    setBusy(true)
    const form = new FormData()
    form.append('file', file)
    try {
      const a = await api.upload<Asset>('/assets', form)
      setMsg({
        tone: 'green',
        text: a.nft_token_id
          ? `Uploaded ${a.name} — SHA-256 ${a.file_hash.slice(0, 16)}… · NFT #${a.nft_token_id} minted (tx ${a.chain_tx_hash?.slice(0, 12)}…)`
          : `Uploaded ${a.name} — SHA-256 ${a.file_hash.slice(0, 16)}… (chain disabled → NFT pending)`,
      })
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      await refresh()
    } catch (e: any) {
      setMsg({ tone: 'red', text: `Upload failed: ${e.message}` })
    } finally {
      setBusy(false)
    }
  }

  async function addPolicy() {
    setMsg(null)
    try {
      await api.post(`/assets/${policy.asset_id}/policy`, {
        requester_role: policy.role,
        purpose: policy.purpose,
        min_trust: Number(policy.min_trust),
        expires_at: null,
        location_scope: policy.location_scope || null,
        location_strict: policy.location_strict,
        time_start: policy.time_start || null,
        time_end: policy.time_end || null,
      })
      setMsg({
        tone: 'green',
        text: `Policy added: role=${policy.role} · purpose=${policy.purpose} · min_trust=${policy.min_trust}${
          policy.location_scope ? ` · location=${policy.location_scope}${policy.location_strict ? ' (strict)' : ''}` : ''
        }${policy.time_start ? ` · ${policy.time_start}–${policy.time_end}` : ''}`,
      })
    } catch (e: any) {
      setMsg({ tone: 'red', text: `Policy failed: ${e.message}` })
    }
  }

  async function runTransfer() {
    setMsg(null)
    if (!transfer.asset_id || !transfer.to_user_id) return
    try {
      await api.post(`/assets/${transfer.asset_id}/transfer`, { to_user_id: transfer.to_user_id, reason: 'demo handover' })
      setMsg({ tone: 'green', text: 'NFT ownership transferred — recorded as a first-class audit event.' })
      setTransfer({ asset_id: '', to_user_id: '' })
      await refresh()
    } catch (e: any) {
      setMsg({ tone: 'red', text: `Transfer failed: ${e.message}` })
    }
  }

  async function download(id: string) {
    setMsg(null)
    setPipeline(null)
    try {
      const blob = await api.download(`/assets/${id}/content`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `decrypted-${id.slice(0, 8)}.bin`
      a.click()
      setMsg({ tone: 'green', text: 'Access ALLOWED — decrypted plaintext downloaded (AES-256-GCM round trip).' })
      onPipeline({ status: 'ok', decision: 'ALLOW' })
    } catch (e: any) {
      const r = { status: 'denied', detail: e?.detail }
      setPipeline(r)
      onPipeline(e?.detail)
      const decision = typeof e?.detail === 'object' ? e.detail?.decision : undefined
      setMsg({
        tone: decision === 'ALLOW' ? 'green' : decision === 'STEP_UP' ? 'amber' : 'red',
        text: decision
          ? `Access ${decision} — ${e.detail?.human ?? e.detail?.reasons?.join(', ')}`
          : `Access denied: ${e.message ?? ''}`,
      })
    }
  }

  const others = users.filter((u) => u.id !== user?.id)

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <Panel
        title="Encrypted upload"
        subtitle="AES-256-GCM encrypt → SHA-256 hash → optional ERC-721 NFT mint"
        icon={<UploadIcon className="h-5 w-5" />}
        help="The file is encrypted at rest and only its SHA-256 hash is stored. Uploading also mints an ERC-721 ownership token (best-effort) whenever the chain is enabled."
      >
        <div className="space-y-3.5">
          <label
            className={cn(
              'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 py-8 text-center transition',
              dragging || file
                ? 'border-brand-500 bg-brand-50'
                : 'border-slate-300 bg-white hover:border-brand-400',
            )}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0])
            }}
          >
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <div className="grid h-12 w-12 place-items-center rounded-2xl border border-brand-200 bg-brand-50 text-brand-600">
              <UploadIcon className="h-6 w-6" />
            </div>
            {file ? (
              <>
                <span className="max-w-full truncate text-sm font-medium text-slate-800">{file.name}</span>
                <span className="text-[11px] text-slate-500">{(file.size / 1024).toFixed(1)} KB · drop another file to replace</span>
              </>
            ) : (
              <>
                <span className="text-sm font-medium text-slate-700">Drop a file here or click to browse</span>
                <span className="text-[11px] text-slate-500">Encrypted before the SHA-256 hash is recorded — NFT minted on upload when chain is on</span>
              </>
            )}
          </label>

          <BtnPrimary className="w-full" onClick={upload} disabled={!file || busy}>
            {busy && <Spinner />}
            {busy ? 'Encrypting…' : 'Encrypt + store'}
          </BtnPrimary>
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        </div>
      </Panel>

      <Panel
        title="Access policy (ABAC)"
        subtitle="Owner defines role + purpose + min trust + optional context constraints"
        icon={<FolderLockIcon className="h-5 w-5" />}
        help="V2 policies can optionally declare location scope (policy-based, e.g. a campus or branch) and business hours. Requesters declare context via headers — strict policies DENY a missing/mismatched location, non-strict ones degrade to read-only RESTRICTED."
      >
        <div className="space-y-3.5">
          <Field label="Asset" hint="which document the policy covers">
            <Select value={policy.asset_id} onChange={(e) => setPolicy({ ...policy, asset_id: e.target.value })}>
              <option value="">Select asset…</option>
              {assets
                .filter((a) => a.owner_id === user?.id || user?.role === 'admin')
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.id.slice(0, 8)}…)
                  </option>
                ))}
            </Select>
          </Field>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Role">
              <Select value={policy.role} onChange={(e) => setPolicy({ ...policy, role: e.target.value })}>
                <option value="verifier">verifier</option>
                <option value="issuer">issuer</option>
                <option value="holder">holder</option>
              </Select>
            </Field>
            <Field label="Purpose">
              <Input value={policy.purpose} onChange={(e) => setPolicy({ ...policy, purpose: e.target.value })} placeholder="employment" />
            </Field>
            <Field label="Min trust">
              <Input
                type="number"
                min={0}
                max={100}
                value={policy.min_trust}
                onChange={(e) => setPolicy({ ...policy, min_trust: e.target.value })}
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Location scope" hint="optional, policy-based">
              <Input
                value={policy.location_scope}
                onChange={(e) => setPolicy({ ...policy, location_scope: e.target.value })}
                placeholder="e.g. Mumbai HQ (responder declares)"
              />
            </Field>
            <Field label="Business hours" hint="HH:MM (optional)">
              <div className="flex items-center gap-1.5">
                <Input type="time" value={policy.time_start} onChange={(e) => setPolicy({ ...policy, time_start: e.target.value })} />
                <span className="text-slate-400">–</span>
                <Input type="time" value={policy.time_end} onChange={(e) => setPolicy({ ...policy, time_end: e.target.value })} />
              </div>
            </Field>
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-600">
            <input
              type="checkbox"
              checked={policy.location_strict}
              onChange={(e) => setPolicy({ ...policy, location_strict: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            Strict location (mismatch → DENY; non-strict → RESTRICTED read-only)
          </label>
          <BtnPrimary className="w-full" onClick={addPolicy} disabled={!policy.asset_id}>
            Add policy
          </BtnPrimary>
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        </div>
      </Panel>

      <div className="lg:col-span-2">
        <Panel
          title="Assets"
          subtitle="Encrypted at rest, hash-shared, NFT-ownership tracked. Evaluate runs the 4-way pipeline."
          icon={<LockIcon className="h-5 w-5" />}
          help="Each asset row shows its SHA-256 proof + optional NFT id + anchor tx. Owners can transfer the NFT ownership token to another user — an anchored, first-class event."
        >
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
              <ShieldAlertIcon className="h-4 w-4 text-brand-600" />
              Header <code className="rounded bg-white px-1 font-mono text-[10px]">X-TrustVault-Location-Scope</code>{' '}
              declares location for policy checks.
            </div>
            {assets.length === 0 ? (
              <EmptyState
                icon={<FileTextIcon className="h-5 w-5" />}
                title="No assets yet"
                hint="Upload a file to see it encrypted, hashed and tracked — then define a policy and evaluate controlled access."
              />
            ) : (
              <div className="space-y-3">
                {assets.map((a) => (
                  <div key={a.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex min-w-0 items-start gap-3">
                        <div className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-brand-100 bg-brand-50 text-brand-600">
                          <FileTextIcon className="h-4 w-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="truncate text-sm font-semibold text-slate-800">{a.name}</span>
                            {a.owner_id === user?.id && <Badge tone="slate">mine</Badge>}
                            {a.nft_token_id && (
                              <Tip label="ERC-721 ownership token on the AssetRegistry. Transfer changes the owner on this platform and records the event.">
                                <Badge tone="brand">
                                  NFT #{a.nft_token_id}
                                </Badge>
                              </Tip>
                            )}
                          </div>
                          <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 font-mono text-[10px] text-slate-500">
                            <span title={a.file_hash}>sha256 {a.file_hash.slice(0, 26)}…</span>
                            <span>{a.encrypted_uri}</span>
                            <span>cid {a.cid ?? 'none (local storage MVP)'}</span>
                            {a.chain_tx_hash && <span title={a.chain_tx_hash}>tx {a.chain_tx_hash.slice(0, 14)}…</span>}
                          </div>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <div className="flex items-center gap-2">
                          {a.owner_id === user?.id && (
                            <Select
                              value={transfer.asset_id === a.id ? transfer.to_user_id : ''}
                              onChange={(e) => setTransfer({ asset_id: a.id, to_user_id: e.target.value })}
                              className="!w-44 !px-2 !py-1.5 text-xs"
                              title="Transfer NFT ownership to another user"
                            >
                              <option value="">Transfer to…</option>
                              {others.map((u) => (
                                <option key={u.id} value={u.id}>
                                  {u.email} ({u.role})
                                </option>
                              ))}
                            </Select>
                          )}
                          {transfer.asset_id === a.id && transfer.to_user_id && (
                            <BtnGhost className="!px-3 !py-1.5 text-xs" onClick={runTransfer}>
                              <GiveIcon className="h-3.5 w-3.5" />
                              Transfer
                            </BtnGhost>
                          )}
                          <BtnGhost className="!px-3 !py-1.5 text-xs" onClick={() => download(a.id)}>
                            <ArrowDownIcon className="h-3.5 w-3.5" />
                            Evaluate access
                          </BtnGhost>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {pipeline && <PipelineResult body={pipeline} />}
          </div>
        </Panel>
      </div>
    </div>
  )
}

type NoticeState = { tone: 'green' | 'red' | 'amber' | 'slate'; text: string }