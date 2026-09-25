import { useCallback, useEffect, useState } from 'react'
import { FingerprintIcon, KeyIcon, ServerIcon, ShieldIcon, UserIcon } from './icons'
import { Badge, BtnGhost, BtnPrimary, Field, Input, Notice, Panel, Spinner } from './ui'
import { authApi, dashboardApi, orgApi, type CurrentUser, type Organization, type TrustedDevice } from '../api'

export default function SettingsPanel({ user }: { user: CurrentUser }) {
  const [msg, setMsg] = useState<{ tone: 'green' | 'red'; text: string } | null>(null)

  // Devices
  const [devices, setDevices] = useState<TrustedDevice[]>([])
  const [newDeviceLabel, setNewDeviceLabel] = useState('')

  // Change password
  const [curPass, setCurPass] = useState('')
  const [newPass, setNewPass] = useState('')
  const [confirmPass, setConfirmPass] = useState('')
  const [busyPw, setBusyPw] = useState(false)

  // Organization
  const [myOrg, setMyOrg] = useState<Organization | null>(null)
  const [orgName, setOrgName] = useState('')
  const [orgDomain, setOrgDomain] = useState('')
  const [busyOrg, setBusyOrg] = useState(false)

  // Infrastructure
  const [tech, setTech] = useState<{ flags?: any; chain?: any } | null>(null)

  const notify = (text: string, tone: 'green' | 'red' = 'green') => setMsg({ tone, text })

  const loadDevices = useCallback(async () => {
    try {
      setDevices(await authApi.devices())
    } catch { /* no-op */ }
  }, [])

  useEffect(() => {
    loadDevices()
    orgApi.me().then(setMyOrg).catch(() => {})
    dashboardApi
      .summary(true)
      .then((s) => setTech(s.technical))
      .catch(() => {})
  }, [loadDevices])

  async function changePassword() {
    setMsg(null)
    if (!curPass || !newPass) {
      notify('Both current and new password are required.', 'red')
      return
    }
    if (newPass !== confirmPass) {
      notify('New passwords do not match.', 'red')
      return
    }
    setBusyPw(true)
    try {
      await authApi.changePassword(curPass, newPass)
      notify('Password updated. Use it the next time you sign in.')
      setCurPass(''); setNewPass(''); setConfirmPass('')
    } catch (e: any) {
      notify(e.message || 'Could not change password.', 'red')
    } finally {
      setBusyPw(false)
    }
  }

  async function applyOrg() {
    setMsg(null)
    setBusyOrg(true)
    try {
      const org = await orgApi.apply(orgName.trim(), orgDomain.trim())
      setMyOrg(org)
      notify(`Application submitted for “${org.name}”. An administrator will review it.`)
      setOrgName(''); setOrgDomain('')
    } catch (e: any) {
      notify(e.message || 'Application failed.', 'red')
    } finally {
      setBusyOrg(false)
    }
  }

  async function removeDevice(id: string) {
    setMsg(null)
    try {
      await authApi.removeDevice(id)
      notify('Device removed.')
      await loadDevices()
    } catch (e: any) {
      notify(e.message || 'Could not remove device.', 'red')
    }
  }

  const infos: { label: string; value: string; tone?: string }[] = [
    { label: 'Email', value: user.email },
    { label: 'Role', value: user.role },
    { label: 'Status', value: user.status },
    { label: 'DID', value: user.did ?? '—', tone: 'font-mono text-[10px] text-slate-400' },
  ]

  return (
    <div className="space-y-6 max-w-3xl animate-fade-up">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-slate-900">Account & Security Settings</h2>
        <p className="text-xs text-slate-500">Managed from live account, device and platform configuration</p>
      </div>

      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}

      {/* Account */}
      <Panel title="Account" icon={<UserIcon className="h-5 w-5" />}>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4 text-xs">
          {infos.map((i) => (
            <div key={i.label}>
              <dt className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">{i.label}</dt>
              <dd className={`mt-1 text-sm font-bold text-slate-800 ${i.tone ?? ''}`}>{i.value}</dd>
            </div>
          ))}
        </dl>
      </Panel>

      {/* Devices */}
      <Panel title="Trusted devices" subtitle="Devices that hold trust for this account" icon={<FingerprintIcon className="h-5 w-5" />}>
        <div className="space-y-3">
          {devices.length === 0 && <p className="text-xs text-slate-400">No trusted devices recorded for this account.</p>}
          {devices.map((d) => (
            <div key={d.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs">
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-bold text-slate-900">{d.label}</p>
                  <Badge tone={d.status === 'active' ? 'green' : 'red'} dot>{d.status}</Badge>
                </div>
                <p className="mt-0.5 text-[11px] text-slate-500">
                  {[d.browser, d.os].filter(Boolean).join(' · ') || 'unknown client'} · last seen {new Date(d.last_seen).toLocaleString()}
                </p>
              </div>
              <BtnGhost className="!px-3 !py-1.5 text-[11px] text-rose-600 border border-rose-200" onClick={() => removeDevice(d.id)}>
                Remove
              </BtnGhost>
            </div>
          ))}
          <div className="flex items-end gap-3 pt-2">
<div className="flex-1">
            <Field label="Register this device">
              <Input value={newDeviceLabel} onChange={(e) => setNewDeviceLabel(e.target.value)} placeholder="e.g. Work laptop" />
            </Field>
          </div>
            <BtnPrimary
              className="!py-2.5"
              disabled={!newDeviceLabel.trim()}
              onClick={async () => {
                setMsg(null)
                try {
                  await authApi.registerDevice(newDeviceLabel.trim())
                  notify('Device registered.')
                  setNewDeviceLabel('')
                  await loadDevices()
                } catch (e: any) {
                  notify(e.message || 'Could not register device.', 'red')
                }
              }}
            >
              Trust it
            </BtnPrimary>
          </div>
        </div>
      </Panel>

      {/* Change password */}
      <Panel title="Change password" icon={<KeyIcon className="h-5 w-5" />}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label="Current password">
            <Input type="password" value={curPass} onChange={(e) => setCurPass(e.target.value)} />
          </Field>
          <Field label="New password">
            <Input type="password" value={newPass} onChange={(e) => setNewPass(e.target.value)} />
          </Field>
          <Field label="Confirm new password">
            <Input type="password" value={confirmPass} onChange={(e) => setConfirmPass(e.target.value)} />
          </Field>
        </div>
        <div className="mt-4">
          <BtnPrimary onClick={changePassword} disabled={busyPw}>
            {busyPw && <Spinner />}
            Update password
          </BtnPrimary>
        </div>
      </Panel>

      {/* Organization */}
      <Panel title="Organization" icon={<ServerIcon className="h-5 w-5" />}>
        {myOrg ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs space-y-1.5">
            <div className="flex items-center justify-between">
              <p className="font-bold text-slate-900">{myOrg.name}</p>
              <Badge tone={myOrg.verification_status === 'approved' ? 'green' : 'amber'} dot>{myOrg.verification_status}</Badge>
            </div>
            <p className="text-slate-500">
              {myOrg.official_domain} · identifier {myOrg.org_identifier ?? '—'}
            </p>
            {myOrg.verification_status !== 'approved' && (
              <p className="text-[11px] text-slate-500">Once approved your role becomes <b>issuer</b> and you can issue credentials on behalf of this institution.</p>
            )}
          </div>
        ) : (
          <div className="space-y-3.5">
            <p className="text-xs text-slate-500">
              Holders can apply to join a verified institution. Approval upgrades your role to <b>issuer</b>.
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Institution name">
                <Input value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder="e.g. Saveetha School of Engineering" />
              </Field>
              <Field label="Official domain">
                <Input value={orgDomain} onChange={(e) => setOrgDomain(e.target.value)} placeholder="e.g. saveetha.ac.in" />
              </Field>
            </div>
            <BtnPrimary onClick={applyOrg} disabled={busyOrg || !orgName.trim() || !orgDomain.trim()}>
              {busyOrg && <Spinner />}
              Apply to join
            </BtnPrimary>
          </div>
        )}
      </Panel>

      {/* Background infrastructure */}
      <Panel title="Background infrastructure" subtitle="Read live from backend configuration" icon={<ShieldIcon className="h-5 w-5" />}>
        <div className="space-y-3 text-xs text-slate-600">
          <div className="flex items-center justify-between py-2 border-b border-slate-100">
            <span className="font-semibold text-slate-800">Blockchain anchoring</span>
            <span className={`font-mono font-bold ${tech?.flags?.chain_enabled ? 'text-emerald-600' : 'text-slate-400'}`}>
              {tech?.flags?.chain_enabled ? 'enabled' : 'disabled'}
            </span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-slate-100">
            <span className="font-semibold text-slate-800">Audit registry</span>
            <span className="font-mono text-[10px] text-slate-500 truncate">{tech?.chain?.audit_registry ?? 'not configured'}</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-slate-100">
            <span className="font-semibold text-slate-800">Asset registry</span>
            <span className="font-mono text-[10px] text-slate-500 truncate">{tech?.chain?.asset_registry ?? 'not configured'}</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-slate-100">
            <span className="font-semibold text-slate-800">RPC configured</span>
            <span className={`font-mono font-bold ${tech?.chain?.rpc_configured ? 'text-emerald-600' : 'text-slate-400'}`}>
              {tech?.chain?.rpc_configured ? 'yes' : 'no'}
            </span>
          </div>
          <div className="flex items-center justify-between py-2">
            <span className="font-semibold text-slate-800">QR verification expiry</span>
            <span className="font-mono text-slate-500">{tech?.flags?.qr_expiry_minutes ?? '—'} minutes</span>
          </div>
        </div>
      </Panel>
    </div>
  )
}