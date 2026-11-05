import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import DoorStatus from '../components/DoorStatus.jsx'
import LiveStream from '../components/LiveStream.jsx'
import { useDashboardSocket } from '../hooks/useDashboardSocket.js'
import { api, getApiErrorMessage } from '../services/api.js'
import { mockEventsEnabled } from '../services/mock.js'
import { getReasonLabel } from '../services/reasons.js'

function startOfLocalDayIso() {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  return start.toISOString()
}

function formatTime(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString('vi-VN')
}

function StatusChip({ label, state, tone = 'neutral' }) {
  return (
    <div className="status-item">
      <span>{label}</span>
      <span className={`status-chip status-chip--${tone}`}>{state}</span>
    </div>
  )
}

function fireMockEvent(event, data) {
  window.dispatchEvent(new CustomEvent('dashboard:mock-event', { detail: { event, data } }))
}

export default function Dashboard() {
  const { connected, lastResult, cameraStatus, aiStatus, recording, doorState } = useDashboardSocket()
  const [logs, setLogs] = useState([])
  const [mockLogs, setMockLogs] = useState([])
  const [logsLoading, setLogsLoading] = useState(true)
  const [logsError, setLogsError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [streamState, setStreamState] = useState({ enabled: false, error: false })

  useEffect(() => {
    let active = true
    setLogsLoading(true)
    setLogsError('')
    api.get('/logs', { params: { from: startOfLocalDayIso(), limit: 200 } })
      .then(({ data }) => {
        if (active) setLogs(Array.isArray(data) ? data : [])
      })
      .catch((error) => {
        if (active) setLogsError(getApiErrorMessage(error, 'Không tải được hoạt động hôm nay.'))
      })
      .finally(() => {
        if (active) setLogsLoading(false)
      })
    return () => { active = false }
  }, [lastResult, refreshKey])

  const handleStreamStatus = useCallback((status) => setStreamState(status), [])
  const combinedLogs = useMemo(() => [...mockLogs, ...logs]
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()), [logs, mockLogs])
  const recentLogs = combinedLogs.slice(0, 10)
  const grantedCount = combinedLogs.filter((item) => item.decision === 'granted').length
  const deniedCount = combinedLogs.filter((item) => item.decision === 'denied').length
  const latestAnnouncement = lastResult?.announcement

  const simulateEvents = () => {
    // TODO: bỏ bộ phát giả sau khi nghiệm thu luồng event WebSocket thật.
    const now = new Date().toISOString()
    const announcement = {
      display: 'Nguyễn Văn An ở phòng A-1203 đã vào chung cư lúc 9 giờ 25 phút.',
      spoken: 'Nguyễn Văn An ở phòng A một hai không ba đã vào chung cư lúc chín giờ hai mươi lăm phút.',
      kind: 'granted',
    }
    const accessResult = {
      timestamp: now,
      name: 'Nguyễn Văn An',
      decision: 'granted',
      reason: 'ok',
      similarity: 0.94,
      liveness: true,
      announcement,
    }
    setMockLogs((items) => [accessResult, ...items].slice(0, 10))
    fireMockEvent('access_result', accessResult)
    fireMockEvent('ai_status', { running: true, fps: 5.8, tracking: true, last_event_at: now })
    fireMockEvent('record_progress', { t_ms: 1800, got: 18, kept: 16 })
  }

  const cameraLabel = cameraStatus?.running ? 'Đang hoạt động' : cameraStatus ? 'Chưa sẵn sàng' : 'Đang kiểm tra'
  const aiLabel = aiStatus?.running ? 'Đang hoạt động' : aiStatus ? 'Đang dừng' : 'Đang kiểm tra'
  const streamLabel = streamState.error ? 'Lỗi tải' : streamState.enabled ? 'Đang xem' : 'Đang tắt'

  return (
    <main className="page dashboard-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">SMART ACCESS</p>
          <h1>Tổng quan</h1>
          <p className="muted">Giám sát camera và hoạt động ra vào theo thời gian thực.</p>
        </div>
        <div className="page-actions">
          <Link className="button button--primary" to="/residents">Quản lý cư dân</Link>
          {mockEventsEnabled && <button type="button" onClick={simulateEvents}>Mô phỏng sự kiện</button>}
        </div>
      </header>

      <section className="status-grid" aria-label="Trạng thái hệ thống">
        <StatusChip label="Kết nối WebSocket" state={connected ? 'Đã kết nối' : 'Đang kết nối lại'} tone={connected ? 'good' : 'warning'} />
        <StatusChip label="Camera" state={cameraLabel} tone={cameraStatus?.running ? 'good' : 'warning'} />
        <StatusChip label="AI" state={aiLabel} tone={aiStatus?.running ? 'good' : 'neutral'} />
        <StatusChip label="Stream" state={streamLabel} tone={streamState.error ? 'bad' : streamState.enabled ? 'good' : 'neutral'} />
        <StatusChip label="Loa" state="Chưa bật" tone="neutral" />
      </section>

      <section className="metric-grid" aria-label="Số liệu trong ngày">
        <article className="metric-card"><span>Tổng lượt hôm nay</span><strong>{combinedLogs.length}</strong></article>
        <article className="metric-card"><span>Được cho phép</span><strong>{grantedCount}</strong></article>
        <article className="metric-card"><span>Bị từ chối</span><strong>{deniedCount}</strong></article>
      </section>

      <section className="dashboard-grid">
        <article className="panel latest-event">
          <div className="section-heading"><div><p className="eyebrow">CẬP NHẬT MỚI NHẤT</p><h2>Sự kiện nhận diện</h2></div></div>
          {latestAnnouncement ? (
            <>
              <p className="announcement">{latestAnnouncement.display}</p>
              <p className="muted spoken-line">Loa đọc: {latestAnnouncement.spoken}</p>
            </>
          ) : (
            <p className="empty-state">Chưa có sự kiện nhận diện mới. Dashboard sẽ tự cập nhật khi có lượt ra vào.</p>
          )}
          {recording && (
            <div className="recording-preview" aria-live="polite">
              <div className="recording-preview__label"><strong>Đang ghi nhận khuôn mặt</strong><span>{recording.got ?? 0} khung · giữ {recording.kept ?? 0}</span></div>
              <div className="progress-track"><span style={{ width: `${Math.max(0, Math.min(100, ((recording.t_ms || 0) / 3000) * 100))}%` }} /></div>
            </div>
          )}
        </article>

        <article className="panel stream-panel">
          <div className="section-heading"><div><p className="eyebrow">CAMERA</p><h2>Xem trực tiếp</h2></div></div>
          <LiveStream cameraStatus={cameraStatus} connected={connected} onStatusChange={handleStreamStatus} />
        </article>
      </section>

      <section className="dashboard-grid dashboard-grid--bottom">
        <article className="panel activity-panel">
          <div className="section-heading">
            <div><p className="eyebrow">HÔM NAY</p><h2>Hoạt động gần đây</h2></div>
            <button type="button" onClick={() => setRefreshKey((key) => key + 1)} disabled={logsLoading}>Làm mới</button>
          </div>
          {logsLoading && <p className="loading-state" role="status">Đang tải hoạt động…</p>}
          {!logsLoading && logsError && (
            <div className="error-state" role="alert"><p>{logsError}</p><button type="button" onClick={() => setRefreshKey((key) => key + 1)}>Thử lại</button></div>
          )}
          {!logsLoading && !logsError && recentLogs.length === 0 && <p className="empty-state">Chưa có lượt ra vào nào hôm nay.</p>}
          {!logsLoading && recentLogs.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Giờ</th><th>Cư dân</th><th>Độ giống</th><th>Chống giả mạo</th><th>Kết quả</th><th>Lý do</th></tr></thead>
                <tbody>{recentLogs.map((item, index) => (
                  <tr key={`${item.timestamp}-${item.name}-${index}`}>
                    <td>{formatTime(item.timestamp)}</td>
                    <td>{item.name || 'Không xác định'}</td>
                    <td>{typeof item.similarity === 'number' ? item.similarity.toFixed(2) : '—'}</td>
                    <td>{item.liveness === true ? 'Đạt' : item.liveness === false ? 'Không đạt' : '—'}</td>
                    <td><span className={`result-chip ${item.decision === 'granted' ? 'result-chip--good' : 'result-chip--bad'}`}>{item.decision === 'granted' ? 'Cho phép' : 'Từ chối'}</span></td>
                    <td>{getReasonLabel(item.reason)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </article>

        <article className="panel door-panel">
          <div className="section-heading"><div><p className="eyebrow">THIẾT BỊ</p><h2>Điều khiển cửa</h2></div></div>
          <DoorStatus doorState={doorState} />
        </article>

        <article className="panel speaker-panel">
          <div className="section-heading"><div><p className="eyebrow">THIẾT BỊ</p><h2>Thông báo bằng loa</h2></div></div>
          <p className="empty-state">Loa chưa được bật ở backend.</p>
          {/* TODO B14: bật nút khi API loa sẵn sàng, rồi gọi POST /api/speaker/mute. */}
          <button type="button" disabled title="Chức năng này chưa sẵn sàng ở backend">Tắt loa</button>
        </article>
      </section>
    </main>
  )
}
