// Agent 3 — giao diện mẫu: docs/demo/smart-access-demo.html
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext.jsx'
import ProtectedRoute from './components/auth/ProtectedRoute.jsx'
import Layout from './components/layout/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Residents from './pages/Residents.jsx'
import Verify from './pages/Verify.jsx'
import AccessLogs from './pages/AccessLogs.jsx'
import AuditLogs from './pages/AuditLogs.jsx'
import Login from './pages/Login.jsx'
import Forbidden from './pages/Forbidden.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/403" element={<Forbidden />} />
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/residents" element={<Residents />} />
              <Route path="/verify" element={<Verify />} />
              <Route path="/logs" element={<AccessLogs />} />
            </Route>
          </Route>
          <Route element={<ProtectedRoute managerOnly />}>
            <Route element={<Layout />}>
              <Route path="/audit" element={<AuditLogs />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
