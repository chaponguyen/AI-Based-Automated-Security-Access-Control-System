// Agent 3 — giao diện mẫu: docs/demo/smart-access-demo.html
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import Residents from './pages/Residents.jsx'
import Verify from './pages/Verify.jsx'
import AccessLogs from './pages/AccessLogs.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <nav className="app-nav" aria-label="Điều hướng chính"><NavLink to="/">Tổng quan</NavLink><NavLink to="/residents">Cư dân</NavLink><NavLink to="/verify">Xác thực</NavLink><NavLink to="/logs">Nhật ký</NavLink></nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/residents" element={<Residents />} />
        <Route path="/verify" element={<Verify />} />
        <Route path="/logs" element={<AccessLogs />} />
      </Routes>
    </BrowserRouter>
  )
}
