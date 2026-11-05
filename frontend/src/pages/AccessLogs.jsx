import { useCallback, useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import Badge from '../components/ui/Badge.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import FormField from '../components/ui/FormField.jsx'
import Input from '../components/ui/Input.jsx'
import Select from '../components/ui/Select.jsx'
import Table from '../components/ui/Table.jsx'
import Toast from '../components/ui/Toast.jsx'
import { api, getApiErrorMessage } from '../services/api.js'
import { mockAdminEnabled, mockDeleteLogs, mockFilterDeletedLogs } from '../services/mock.js'
import { getReasonLabel } from '../services/reasons.js'
import { dateInputBoundaryToISOString, formatDateTime } from '../utils/time.js'

export default function AccessLogs() {
  const { user } = useOutletContext() || {}
  const isManager = user?.role === 'manager'
  const [query, setQuery] = useState('')
  const [decision, setDecision] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [selectedIds, setSelectedIds] = useState(() => new Set())
  const [deleteMode, setDeleteMode] = useState(null)
  const [deleteCount, setDeleteCount] = useState(0)
  const [countLoading, setCountLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [notice, setNotice] = useState('')

  const loadLogs = useCallback(async (activeRef = { current: true }) => {
    setLoading(true)
    setError('')
    if (fromDate && toDate && fromDate > toDate) {
      setError('Ngày bắt đầu phải trước ngày kết thúc.')
      setLoading(false)
      return
    }
    const params = { limit: 1000 }
    if (query.trim()) params.q = query.trim()
    if (decision) params.decision = decision
    if (fromDate) params.from = dateInputBoundaryToISOString(fromDate)
    if (toDate) params.to = dateInputBoundaryToISOString(toDate, true)
    try {
      const { data } = await api.get('/logs', { params })
      if (activeRef.current) setLogs(mockAdminEnabled ? mockFilterDeletedLogs(Array.isArray(data) ? data : []) : Array.isArray(data) ? data : [])
    } catch (requestError) {
      if (activeRef.current) setError(getApiErrorMessage(requestError, 'Không tải được nhật ký ra vào.'))
    } finally {
      if (activeRef.current) setLoading(false)
    }
  }, [query, decision, fromDate, toDate])

  useEffect(() => {
    const active = { current: true }
    const timer = window.setTimeout(() => { void loadLogs(active) }, 300)
    return () => {
      active.current = false
      window.clearTimeout(timer)
    }
  }, [loadLogs, retryKey])

  useEffect(() => {
    setSelectedIds((current) => new Set([...current].filter((id) => logs.some((row) => String(row.id) === String(id)))) )
  }, [logs])

  const toggleSelected = (id) => {
    if (!isManager) return
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (!isManager) return
    const ids = logs.map((row) => row.id).filter((id) => id !== undefined && id !== null)
    setSelectedIds((current) => ids.every((id) => current.has(id)) ? new Set() : new Set(ids))
  }

  const openSelectedDelete = () => {
    if (!isManager || !selectedIds.size) return
    setDeleteError('')
    setDeleteCount(selectedIds.size)
    setDeleteMode('selected')
  }

  const openRangeDelete = async () => {
    if (!isManager) return
    if (!fromDate || !toDate) {
      setDeleteError('Chọn cả ngày bắt đầu và ngày kết thúc để xóa theo khoảng thời gian.')
      return
    }
    if (fromDate > toDate) {
      setDeleteError('Ngày bắt đầu phải trước ngày kết thúc.')
      return
    }
    setCountLoading(true)
    setDeleteError('')
    try {
      const { data } = await api.get('/logs', { params: { from: dateInputBoundaryToISOString(fromDate), to: dateInputBoundaryToISOString(toDate, true), limit: 10000 } })
      const countRows = mockAdminEnabled ? mockFilterDeletedLogs(Array.isArray(data) ? data : []) : (Array.isArray(data) ? data : [])
      setDeleteCount(countRows.length)
      setDeleteMode('range')
    } catch (requestError) {
      setDeleteError(getApiErrorMessage(requestError, 'Không đếm được số dòng trong khoảng đã chọn.'))
    } finally {
      setCountLoading(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteMode || !isManager || deleteLoading) return
    setDeleteLoading(true)
    setDeleteError('')
    const payload = deleteMode === 'selected'
      ? { ids: [...selectedIds] }
      : { from: dateInputBoundaryToISOString(fromDate), to: dateInputBoundaryToISOString(toDate, true) }
    try {
      const result = mockAdminEnabled ? await mockDeleteLogs(payload, deleteCount) : (await api.post('/logs/delete', payload)).data
      const deleted = Number(result?.deleted ?? deleteCount)
      if (deleteMode === 'selected') {
        const removed = new Set(selectedIds)
        setLogs((rows) => rows.filter((row) => !removed.has(row.id)))
      } else {
        const start = new Date(payload.from).getTime()
        const end = new Date(payload.to).getTime()
        setLogs((rows) => rows.filter((row) => {
          const timestamp = new Date(row.timestamp).getTime()
          return timestamp < start || timestamp > end
        }))
      }
      setSelectedIds(new Set())
      setNotice(`Đã xóa ${deleted} dòng nhật ký.`)
      setDeleteMode(null)
      setRetryKey((key) => key + 1)
    } catch (requestError) {
      setDeleteError(getApiErrorMessage(requestError, 'Không xóa được nhật ký. Vui lòng thử lại.'))
    } finally {
      setDeleteLoading(false)
    }
  }

  const allVisibleSelected = logs.length > 0 && logs.every((row) => selectedIds.has(row.id))
  const columns = useMemo(() => [
    ...(isManager ? [{
      key: 'select',
      label: <input type="checkbox" aria-label="Chọn tất cả nhật ký đang hiển thị" checked={allVisibleSelected} onChange={toggleAll} />,
      render: (row) => <input type="checkbox" aria-label={`Chọn nhật ký ${formatDateTime(row.timestamp)}`} checked={selectedIds.has(row.id)} onChange={() => toggleSelected(row.id)} disabled={row.id === undefined || row.id === null} />,
    }] : []),
    { key: 'timestamp', label: 'Thời gian', render: (row) => formatDateTime(row.timestamp) },
    { key: 'name', label: 'Tên', render: (row) => row.name || row.user?.full_name || 'Không xác định' },
    { key: 'similarity', label: 'Độ giống', render: (row) => typeof row.similarity === 'number' ? row.similarity.toFixed(2) : '—' },
    { key: 'liveness', label: 'Chống giả mạo', render: (row) => row.liveness === true ? 'Đạt' : row.liveness === false ? 'Không đạt' : '—' },
    { key: 'decision', label: 'Kết quả', render: (row) => <Badge tone={row.decision === 'granted' ? 'success' : 'danger'}>{row.decision === 'granted' ? 'Cho phép' : 'Từ chối'}</Badge> },
    { key: 'reason', label: 'Lý do', render: (row) => getReasonLabel(row.reason) },
  ], [isManager, allVisibleSelected, selectedIds, logs])

  return (
    <main className="page logs-page">
      <header className="page-header">
        <div><p className="eyebrow">LỊCH SỬ RA VÀO</p><h1>Nhật ký ra vào</h1><p className="muted">Tra cứu kết quả nhận diện và quyết định ra vào.</p></div>
      </header>
      {notice && <Toast message={notice} tone="success" onClose={() => setNotice('')} />}

      <Card className="logs-panel logs-panel--modern">
        <div className="logs-filters">
          <FormField id="logs-query" label="Tìm theo tên">
            <Input id="logs-query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nhập tên cư dân" />
          </FormField>
          <FormField id="logs-decision" label="Kết quả">
            <Select id="logs-decision" value={decision} onChange={(event) => setDecision(event.target.value)}>
              <option value="">Tất cả kết quả</option><option value="granted">Cho phép</option><option value="denied">Từ chối</option>
            </Select>
          </FormField>
          <FormField id="logs-from" label="Từ ngày"><Input id="logs-from" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} /></FormField>
          <FormField id="logs-to" label="Đến ngày"><Input id="logs-to" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} /></FormField>
        </div>

        {isManager && <div className="logs-manager-actions">
          <span>{selectedIds.size ? `Đã chọn ${selectedIds.size} dòng` : 'Chọn dòng để xóa nhật ký'}</span>
          <div>
            <Button variant="danger" size="sm" onClick={openSelectedDelete} disabled={!selectedIds.size || loading}>Xóa đã chọn</Button>
            <Button variant="danger" size="sm" onClick={() => void openRangeDelete()} loading={countLoading} disabled={loading}>Xóa theo khoảng thời gian</Button>
          </div>
        </div>}

        <Table
          columns={columns}
          rows={logs}
          rowKey={(row, index) => row.id ?? `${row.timestamp}-${index}`}
          loading={loading}
          error={error}
          onRetry={() => setRetryKey((key) => key + 1)}
          emptyTitle="Chưa có lượt xác thực phù hợp"
          emptyDescription="Hãy đổi bộ lọc hoặc chờ hệ thống ghi nhận lượt mới."
          className="logs-table-container"
        />
        {deleteError && !deleteMode && <ErrorState message={deleteError} />}
      </Card>

      <ConfirmDialog
        open={Boolean(deleteMode)}
        onClose={() => { if (!deleteLoading) setDeleteMode(null) }}
        onConfirm={() => void confirmDelete()}
        title={deleteMode === 'range' ? 'Xóa nhật ký theo khoảng thời gian?' : 'Xóa các nhật ký đã chọn?'}
        description={deleteMode === 'range' ? `${fromDate} đến ${toDate}` : `${selectedIds.size} dòng đã chọn`}
        confirmLabel="Xóa nhật ký"
        cancelLabel="Hủy"
        loading={deleteLoading}
        danger
      >
        <p className="logs-delete-warning">SỐ DÒNG sẽ xóa: <strong>{deleteCount}</strong>. Thao tác này không thể hoàn tác.</p>
        {deleteError && <ErrorState message={deleteError} />}
      </ConfirmDialog>
    </main>
  )
}
