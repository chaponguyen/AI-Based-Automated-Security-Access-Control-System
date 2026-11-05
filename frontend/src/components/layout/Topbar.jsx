import { MenuIcon } from '../ui/icons.jsx'

const pageTitles = {
  '/': 'Tổng quan',
  '/residents': 'Cư dân',
  '/verify': 'Xác thực',
  '/logs': 'Nhật ký ra vào',
  '/staff': 'Nhân viên',
  '/audit': 'Nhật ký thao tác',
}

export default function Topbar({ pathname = '/', onMenuClick, user, onLogout }) {
  const title = pageTitles[pathname] || 'Trung tâm vận hành'
  return (
    <header className="app-topbar">
      <div className="app-topbar__heading">
        <button className="app-topbar__menu" type="button" onClick={onMenuClick} aria-label="Mở menu điều hướng">
          <MenuIcon />
        </button>
        <div><span className="app-topbar__eyebrow">SMART ACCESS</span><h1>{title}</h1></div>
      </div>
      <div className="app-topbar__account">
        {user ? (
          <>
            <span className="app-topbar__avatar" aria-hidden="true">{(user.full_name || user.username || '?').slice(0, 1).toLocaleUpperCase('vi')}</span>
            <span className="app-topbar__user"><strong>{user.full_name || user.username}</strong><small>{user.role === 'manager' ? 'Quản lý' : 'Nhân viên an ninh'}</small></span>
            {onLogout && <button type="button" className="app-topbar__logout" onClick={onLogout}>Đăng xuất</button>}
          </>
        ) : <span className="app-topbar__context">Hệ thống kiểm soát ra vào</span>}
      </div>
    </header>
  )
}
