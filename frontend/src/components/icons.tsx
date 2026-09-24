import type { SVGProps } from 'react'

type P = SVGProps<SVGSVGElement>

function S({ children, ...props }: P) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  )
}

export function ShieldIcon(props: P) {
  return (
    <S {...props}>
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m9 12 2 2 4-4" />
    </S>
  )
}

export function ActivityIcon(props: P) {
  return (
    <S {...props}>
      <path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2" />
    </S>
  )
}

export function BadgeCheckIcon(props: P) {
  return (
    <S {...props}>
      <path d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76" />
      <path d="m9 12 2 2 4-4" />
    </S>
  )
}

export function FolderLockIcon(props: P) {
  return (
    <S {...props}>
      <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
      <rect x="8.5" y="13" width="7" height="4.5" rx="1" />
      <path d="M10.5 13v-1.5a1.5 1.5 0 0 1 3 0V13" />
    </S>
  )
}

export function KeyIcon(props: P) {
  return (
    <S {...props}>
      <path d="m21 2-2 2" />
      <path d="m18 5-2 2" />
      <circle cx="7.5" cy="16.5" r="5" />
      <path d="m10.5 13.5 7.5-7.5" />
      <path d="m15 9 2 2" />
    </S>
  )
}

export function FileTextIcon(props: P) {
  return (
    <S {...props}>
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="M10 9H8" />
      <path d="M16 13H8" />
      <path d="M16 17H8" />
    </S>
  )
}

export function LogOutIcon(props: P) {
  return (
    <S {...props}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="m16 17 5-5-5-5" />
      <path d="M21 12H9" />
    </S>
  )
}

export function ClockIcon(props: P) {
  return (
    <S {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 6v6l4 2" />
    </S>
  )
}

export function CheckIcon(props: P) {
  return (
    <S {...props}>
      <path d="M20 6 9 17l-5-5" />
    </S>
  )
}

export function XIcon(props: P) {
  return (
    <S {...props}>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </S>
  )
}

export function AlertIcon(props: P) {
  return (
    <S {...props}>
      <path d="M21.73 18 13.8 4.5a2 2 0 0 0-3.6 0L2.27 18a2 2 0 0 0 1.73 3h16.53a2 2 0 0 0 1.73-3Z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </S>
  )
}

export function InfoIcon(props: P) {
  return (
    <S {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </S>
  )
}

export function UploadIcon(props: P) {
  return (
    <S {...props}>
      <path d="M12 13v8" />
      <path d="m8 17 4-4 4 4" />
      <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
    </S>
  )
}

export function ArrowDownIcon(props: P) {
  return (
    <S {...props}>
      <path d="M12 5v14" />
      <path d="m19 12-7 7-7-7" />
    </S>
  )
}

export function LockIcon(props: P) {
  return (
    <S {...props}>
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </S>
  )
}

export function UserIcon(props: P) {
  return (
    <S {...props}>
      <circle cx="12" cy="8" r="4" />
      <path d="M20 21a8 8 0 0 0-16 0" />
    </S>
  )
}

export function ChevronRightIcon(props: P) {
  return (
    <S {...props}>
      <path d="m9 18 6-6-6-6" />
    </S>
  )
}

export function PlusIcon(props: P) {
  return (
    <S {...props}>
      <path d="M5 12h14" />
      <path d="M12 5v14" />
    </S>
  )
}

export function FingerprintIcon(props: P) {
  return (
    <S {...props}>
      <path d="M12 11c0 4-1.5 6-3 8" />
      <path d="M8 9a4 4 0 0 1 8 0c0 2-.3 4-1 6" />
      <path d="M6.5 13.5c.4 2 .9 3.4 1.8 4.7" />
      <path d="M16 7.5c.5 1 .7 2.2.7 3.5 0 1.7-.2 3.6-.8 5.2" />
      <path d="M3 18c1-3 2.6-5.6 4-8.2" />
      <path d="M17.5 16c.7-1.8 1.2-3.8 1.5-5.8" />
      <path d="M4.5 12.6c.2-1.8.7-3.4 1.5-4.9" />
    </S>
  )
}

export function CodeIcon(props: P) {
  return (
    <S {...props}>
      <path d="m16 18 6-6-6-6" />
      <path d="m8 6-6 6 6 6" />
    </S>
  )
}

export function DashboardIcon(props: P) {
  return (
    <S {...props}>
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </S>
  )
}

export function QrCodeIcon(props: P) {
  return (
    <S {...props}>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <path d="M14 14h3v3h-3z" />
      <path d="M21 14v3" />
      <path d="M14 21h3" />
    </S>
  )
}

export function ServerIcon(props: P) {
  return (
    <S {...props}>
      <rect x="3" y="4" width="18" height="7" rx="2" />
      <rect x="3" y="13" width="18" height="7" rx="2" />
      <path d="M7 7.5h.01" />
      <path d="M7 16.5h.01" />
    </S>
  )
}

export function GiveIcon(props: P) {
  return (
    <S {...props}>
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
      <path d="M12 15v2" />
    </S>
  )
}

export function RefreshIcon(props: P) {
  return (
    <S {...props}>
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <path d="M21 3v6h-6" />
    </S>
  )
}

export function ShieldAlertIcon(props: P) {
  return (
    <S {...props}>
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="M12 8v4" />
      <path d="M12 16h.01" />
    </S>
  )
}