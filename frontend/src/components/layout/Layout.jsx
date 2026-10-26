import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'
import Topbar from './Topbar.jsx'

export default function Layout({ user, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const { pathname } = useLocation()
  const closeMenu = () => setMenuOpen(false)

  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onNavigate={closeMenu} onClose={closeMenu} userRole={user?.role} />
      <div className="app-main">
        <Topbar pathname={pathname} onMenuClick={() => setMenuOpen((open) => !open)} user={user} onLogout={onLogout} />
        <div className="app-content"><Outlet context={{ user, onLogout }} /></div>
      </div>
    </div>
  )
}
