import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '../services/api.js'
import { mockAuthEnabled, mockGetAuthMe, mockLogin, mockLogout } from '../services/mock.js'
import Toast from '../components/ui/Toast.jsx'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const navigate = useNavigate()
  const location = useLocation()
  const locationRef = useRef(location)
  locationRef.current = location
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    let active = true
    const loadSession = async () => {
      try {
        const currentUser = mockAuthEnabled ? await mockGetAuthMe() : (await api.get('/auth/me')).data
        if (active) setUser(currentUser || null)
      } catch {
        if (active) setUser(null)
      } finally {
        if (active) setReady(true)
      }
    }
    const onExpired = () => {
      setUser(null)
      setToast(null)
      navigate('/login', { replace: true, state: { notice: 'Phiên đăng nhập đã hết hạn', from: locationRef.current } })
    }
    const onToast = (event) => setToast(event.detail || null)
    window.addEventListener('auth:expired', onExpired)
    window.addEventListener('app:toast', onToast)
    void loadSession()
    return () => {
      active = false
      window.removeEventListener('auth:expired', onExpired)
      window.removeEventListener('app:toast', onToast)
    }
  }, [navigate])

  const login = useCallback(async (username, password) => {
    const result = mockAuthEnabled
      ? await mockLogin(username, password)
      : (await api.post('/auth/login', { username, password })).data
    setUser(result)
    setToast(null)
    return result
  }, [])

  const logout = useCallback(async () => {
    try {
      if (mockAuthEnabled) await mockLogout()
      else await api.post('/auth/logout')
    } catch {
      // Kết thúc phiên trên giao diện ngay cả khi backend không phản hồi thao tác đăng xuất.
    } finally {
      setUser(null)
      navigate('/login', { replace: true })
    }
  }, [navigate])

  const value = useMemo(() => ({ user, ready, login, logout }), [user, ready, login, logout])
  return (
    <AuthContext.Provider value={value}>
      {children}
      {toast && <div className="app-global-toast"><Toast tone={toast.tone} message={toast.message} onClose={() => setToast(null)} /></div>}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth phải được dùng bên trong AuthProvider')
  return value
}
