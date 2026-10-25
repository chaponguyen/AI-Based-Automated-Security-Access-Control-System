// Agent 3 — Bảng nhật ký, lọc theo tên và kết quả.
import { useEffect, useState } from 'react'
import LogTable from '../components/LogTable.jsx'
import { api, getApiErrorMessage } from '../services/api.js'

function localDateBoundary(value, endOfDay = false) {
  if (!value) return ''
  const date = new Date(`${value}T${endOfDay ? '23:59:59.999' : '00:00:00'}`)
  return date.toISOString()
}

export default function AccessLogs() {
  const [query, setQuery] = useState('')
  const [decision, setDecision] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    const timer = window.setTimeout(async () => {
      if (fromDate && toDate && fromDate > toDate) {
        setError('Ngày bắt đầu phải trước ngày kết thúc.')
        setLoading(false)
        return
      }

      const params = {}
      if (query.trim()) params.q = query.trim()
      if (decision) params.decision = decision
      if (fromDate) params.from = localDateBoundary(fromDate)
      if (toDate) params.to = localDateBoundary(toDate, true)

      try {
        const { data } = await api.get('/logs', { params })
        if (active) setLogs(Array.isArray(data) ? data : [])
      } catch (requestError) {
        if (active) setError(getApiErrorMessage(requestError, 'Không tải được nhật ký.'))
      } finally {
        if (active) setLoading(false)
      }
    }, 300)

    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [query, decision, fromDate, toDate, retryKey])

  return (
    <main className="page logs-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">LỊCH SỬ RA VÀO</p>
          <h1>Nhật ký</h1>
          <p className="muted">Tra cứu kết quả nhận diện và quyết định ra vào.</p>
        </div>
      </header>

      <section className="panel logs-panel">
        <div className="logs-filters">
          <label className="field" htmlFor="logs-query"><span>Tìm theo tên</span>
            <input id="logs-query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nhập tên cư dân" />
          </label>
          <label className="field" htmlFor="logs-decision"><span>Kết quả</span>
            <select id="logs-decision" value={decision} onChange={(event) => setDecision(event.target.value)}>
              <option value="">Tất cả kết quả</option>
              <option value="granted">Cho phép</option>
              <option value="denied">Từ chối</option>
            </select>
          </label>
          <label className="field" htmlFor="logs-from"><span>Từ ngày</span>
            <input id="logs-from" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
          </label>
          <label className="field" htmlFor="logs-to"><span>Đến ngày</span>
            <input id="logs-to" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} />
          </label>
        </div>

        <div className="logs-results" aria-live="polite">
          {loading && <p className="loading-state" role="status">Đang tải nhật ký…</p>}
          {!loading && error && (
            <div className="error-state" role="alert"><p>{error}</p><button type="button" onClick={() => setRetryKey((key) => key + 1)}>Thử lại</button></div>
          )}
          {!loading && !error && logs.length === 0 && (
            <p className="empty-state">Chưa có lượt xác thực phù hợp. Hãy đổi bộ lọc hoặc chờ hệ thống ghi nhận lượt mới.</p>
          )}
          {!loading && !error && logs.length > 0 && <LogTable rows={logs} />}
        </div>
      </section>
    </main>
  )
}
