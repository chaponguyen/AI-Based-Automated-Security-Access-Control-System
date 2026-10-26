import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import Button from '../components/ui/Button.jsx'
import FormField from '../components/ui/FormField.jsx'
import Input from '../components/ui/Input.jsx'
import Card from '../components/ui/Card.jsx'

export default function Login() {
  const { user, ready, login } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retrySeconds, setRetrySeconds] = useState(0)

  useEffect(() => {
    if (ready && user) navigate(location.state?.from || '/', { replace: true })
  }, [ready, user, navigate, location.state])

  useEffect(() => {
    if (retrySeconds <= 0) return undefined
    const timer = window.setTimeout(() => setRetrySeconds((seconds) => {
      if (seconds <= 1) {
        setError('')
        return 0
      }
      return seconds - 1
    }), 1000)
    return () => window.clearTimeout(timer)
  }, [retrySeconds])

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(username, password)
      const destination = location.state?.from || '/'
      navigate(destination, { replace: true })
    } catch (loginError) {
      const response = loginError?.response
      if (response?.status === 423) {
        const seconds = Math.max(1, Number(response.data?.retry_after_s) || 1)
        setRetrySeconds(seconds)
        setError('Tài khoản tạm khóa.')
      } else if (response?.status === 401) {
        setError('Tên đăng nhập hoặc mật khẩu không đúng')
      } else {
        setError('Không thể kết nối backend. Hãy kiểm tra kết nối rồi thử lại.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-page">
      <Card className="auth-card">
        <div className="auth-brand"><span aria-hidden="true">SA</span><div><strong>Smart Access</strong><small>Kiểm soát ra vào</small></div></div>
        <div className="auth-heading"><p className="eyebrow">KHU VỰC NHÂN VIÊN</p><h1>Đăng nhập</h1><p>Đăng nhập để tiếp tục vào hệ thống.</p></div>
        {location.state?.notice && <p className="auth-notice" role="status">{location.state.notice}</p>}
        <form onSubmit={submit} className="auth-form">
          <FormField id="login-username" label="Tên đăng nhập"><Input id="login-username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required /></FormField>
          <FormField id="login-password" label="Mật khẩu"><Input id="login-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></FormField>
          {error && <p className="auth-error" role="alert">{error}{retrySeconds > 0 && ` Thử lại sau ${retrySeconds} giây.`}</p>}
          <Button type="submit" loading={busy} disabled={busy || retrySeconds > 0}>Đăng nhập</Button>
        </form>
      </Card>
    </main>
  )
}
