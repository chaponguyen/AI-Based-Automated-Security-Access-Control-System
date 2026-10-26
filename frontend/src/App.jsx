// Agent 3 — giao diện mẫu: docs/demo/smart-access-demo.html
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Residents from './pages/Residents.jsx'
import Verify from './pages/Verify.jsx'
import AccessLogs from './pages/AccessLogs.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/residents" element={<Residents />} />
          <Route path="/verify" element={<Verify />} />
          <Route path="/logs" element={<AccessLogs />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
