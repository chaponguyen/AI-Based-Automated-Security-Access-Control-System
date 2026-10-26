import { Link } from 'react-router-dom'
import Card from '../components/ui/Card.jsx'

export default function Forbidden() {
  return <main className="auth-page"><Card className="auth-card auth-forbidden"><p className="eyebrow">403</p><h1>Không có quyền truy cập</h1><p>Tài khoản của bạn không được phép mở trang này.</p><Link to="/">Quay về tổng quan</Link></Card></main>
}
