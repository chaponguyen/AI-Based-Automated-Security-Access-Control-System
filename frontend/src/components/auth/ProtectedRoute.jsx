import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import Spinner from '../ui/Spinner.jsx'

export default function ProtectedRoute({ managerOnly = false }) {
  const { user, ready } = useAuth()
  const location = useLocation()
  if (!ready) return <div className="auth-loading"><Spinner label="Đang kiểm tra phiên đăng nhập" /></div>
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  if (managerOnly && user.role !== 'manager') return <Navigate to="/403" replace />
  return <Outlet />
}
