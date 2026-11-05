import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'
import Topbar from './Topbar.jsx'
import { useAuth } from '../../context/AuthContext.jsx'

export default function Layout() {
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const { pathname } = useLocation()
  const closeMenu = () => setMenuOpen(false)

  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onNavigate={closeMenu} onClose={closeMenu} userRole={user?.role} />
      <div className="app-main">
        <Topbar pathname={pathname} onMenuClick={() => setMenuOpen((open) => !open)} user={user} onLogout={logout} />
        <div className="app-content"><Outlet context={{ user, onLogout: logout }} /></div>
      </div>
    </div>
  )
}
