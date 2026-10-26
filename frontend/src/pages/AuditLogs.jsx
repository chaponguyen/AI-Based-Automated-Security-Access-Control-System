import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import Badge from '../components/ui/Badge.jsx'
import Card from '../components/ui/Card.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import FormField from '../components/ui/FormField.jsx'
import Input from '../components/ui/Input.jsx'
import Select from '../components/ui/Select.jsx'
import Table from '../components/ui/Table.jsx'
import { api, getApiErrorMessage } from '../services/api.js'
import { mockAdminEnabled, mockGetAudit } from '../services/mock.js'

function formatTimestamp(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('vi-VN')
}

export default function AuditLogs() {
  const { user } = useOutletContext() || {}
  const isManager = user?.role === 'manager'
  const [query, setQuery] = useState('')
  const [action, setAction] = useState('')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    if (!isManager) {
      setLoading(false)
      return undefined
    }
    let active = true
    setLoading(true)
    setError('')
    const timer = window.setTimeout(async () => {
      try {
        const params = { limit: 200 }
        if (action) params.action = action
        if (query.trim()) params.q = query.trim()
        const data = mockAdminEnabled ? await mockGetAudit(params) : (await api.get('/audit', { params })).data
        if (active) setRows(Array.isArray(data) ? data : [])
      } catch (requestError) {
        if (active) setError(getApiErrorMessage(requestError, 'Không tải được nhật ký thao tác.'))
      } finally {
        if (active) setLoading(false)
      }
    }, 300)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [isManager, query, action, retryKey])

  if (!isManager) {
    return <main className="page audit-page"><ErrorState title="Không có quyền truy cập" message="Nhật ký thao tác chỉ dành cho quản lý." /></main>
  }

  const columns = [
    { key: 'timestamp', label: 'Thời gian', render: (row) => formatTimestamp(row.timestamp) },
    { key: 'staff_username', label: 'Nhân viên' },
    { key: 'action', label: 'Thao tác', render: (row) => <Badge tone="info">{row.action}</Badge> },
    { key: 'target_type', label: 'Đối tượng' },
    { key: 'target_id', label: 'Mã đối tượng', render: (row) => row.target_id ?? '—' },
    { key: 'detail', label: 'Chi tiết' },
  ]

  return (
    <main className="page audit-page">
      <header className="page-header"><div><p className="eyebrow">QUẢN TRỊ</p><h1>Nhật ký thao tác</h1><p className="muted">Theo dõi hoạt động quản trị. Trang này chỉ xem, không có thao tác xóa.</p></div></header>
      <Card className="audit-panel">
        <div className="audit-filters">
          <FormField id="audit-query" label="Tìm kiếm"><Input id="audit-query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nhân viên, thao tác hoặc đối tượng" /></FormField>
          <FormField id="audit-action" label="Loại thao tác">
            <Select id="audit-action" value={action} onChange={(event) => setAction(event.target.value)}>
              <option value="">Tất cả thao tác</option>
              <option value="door.open">Mở cửa</option>
              <option value="resident.status">Đổi quyền cư dân</option>
              <option value="resident.delete">Xóa cư dân</option>
              <option value="staff.create">Tạo tài khoản</option>
              <option value="staff.update">Cập nhật tài khoản</option>
              <option value="staff.delete">Xóa tài khoản</option>
              <option value="logs.delete">Xóa nhật ký</option>
            </Select>
          </FormField>
        </div>
        <Table
          columns={columns}
          rows={rows}
          rowKey="id"
          loading={loading}
          error={error}
          onRetry={() => setRetryKey((key) => key + 1)}
          emptyTitle="Chưa có thao tác"
          emptyDescription="Thao tác quản trị sẽ được ghi lại tại đây."
          className="audit-table-container"
        />
      </Card>
    </main>
  )
}
