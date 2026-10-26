import { NavLink } from 'react-router-dom'
import { AuditIcon, LogsIcon, OverviewIcon, ResidentsIcon, StaffIcon, VerifyIcon } from '../ui/icons.jsx'

const navigation = [
  { to: '/', label: 'Tổng quan', Icon: OverviewIcon, end: true },
  { to: '/residents', label: 'Cư dân', Icon: ResidentsIcon },
  { to: '/verify', label: 'Xác thực', Icon: VerifyIcon },
  { to: '/logs', label: 'Nhật ký ra vào', Icon: LogsIcon },
  { to: '/staff', label: 'Nhân viên', Icon: StaffIcon, managerOnly: true },
  { to: '/audit', label: 'Nhật ký thao tác', Icon: AuditIcon, managerOnly: true },
]

export default function Sidebar({ open = false, onNavigate, onClose, userRole }) {
  return (
    <>
      {open && <button className="app-sidebar-backdrop" type="button" onClick={onClose} aria-label="Đóng menu điều hướng" />}
      <aside className={`app-sidebar${open ? ' app-sidebar--open' : ''}`} aria-label="Thanh điều hướng">
        <div className="app-sidebar__brand">
          <span className="app-sidebar__brand-mark" aria-hidden="true"><VerifyIcon /></span>
          <span><strong>Smart Access</strong><small>Kiểm soát ra vào</small></span>
        </div>
        <p className="app-sidebar__section">KHÔNG GIAN LÀM VIỆC</p>
        <nav className="app-sidebar__nav" aria-label="Điều hướng chính">
          {navigation.filter((item) => !item.managerOnly || userRole === 'manager').map(({ to, label, Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={onNavigate} className={({ isActive }) => `app-sidebar__link${isActive ? ' app-sidebar__link--active' : ''}`}>
              <Icon /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  )
}
