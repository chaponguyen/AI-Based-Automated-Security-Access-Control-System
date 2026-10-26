function Icon({ children, title, ...props }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
      {...props}
    >
      {title && <title>{title}</title>}
      {children}
    </svg>
  )
}

export const OverviewIcon = (props) => <Icon {...props}><rect x="3" y="3" width="8" height="8" rx="1.5" /><rect x="13" y="3" width="8" height="5" rx="1.5" /><rect x="13" y="10" width="8" height="11" rx="1.5" /><rect x="3" y="13" width="8" height="8" rx="1.5" /></Icon>
export const ResidentsIcon = (props) => <Icon {...props}><path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="10" cy="7" r="4" /><path d="M20 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></Icon>
export const VerifyIcon = (props) => <Icon {...props}><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></Icon>
export const LogsIcon = (props) => <Icon {...props}><path d="M8 6h13M8 12h13M8 18h13" /><path d="M3 6h.01M3 12h.01M3 18h.01" /></Icon>
export const DoorIcon = (props) => <Icon {...props}><path d="M4 21h16M6 21V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v17" /><path d="M14 12h.01" /></Icon>
export const StaffIcon = (props) => <Icon {...props}><circle cx="9" cy="8" r="3.5" /><path d="M3 21v-1a6 6 0 0 1 12 0v1M17 8h4M19 6v4M17 16h4" /></Icon>
export const AuditIcon = (props) => <Icon {...props}><path d="M4 4h16v16H4zM8 8h8M8 12h8M8 16h5" /><path d="M8 2v4M16 2v4" /></Icon>
export const LogoutIcon = (props) => <Icon {...props}><path d="M10 17l5-5-5-5M15 12H3" /><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6" /></Icon>
export const MenuIcon = (props) => <Icon {...props}><path d="M4 6h16M4 12h16M4 18h16" /></Icon>
export const CloseIcon = (props) => <Icon {...props}><path d="m18 6-12 12M6 6l12 12" /></Icon>
