import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import LiveStream from '../components/LiveStream.jsx'
import Badge from '../components/ui/Badge.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import FormField from '../components/ui/FormField.jsx'
import Input from '../components/ui/Input.jsx'
import Table from '../components/ui/Table.jsx'
import { DoorIcon } from '../components/ui/icons.jsx'
import { useDashboardSocket } from '../hooks/useDashboardSocket.js'
import { api, getApiErrorMessage } from '../services/api.js'
import { mockAdminEnabled, mockGetDoorStatus, mockOpenDoor } from '../services/mock.js'
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

function getReportedDoorSeconds(data) {
  const remaining = Number(data?.remaining_seconds)
  if (data?.remaining_seconds !== undefined && data?.remaining_seconds !== null && Number.isFinite(remaining)) {
    return Math.max(0, remaining)
  }
  const openSeconds = Number(data?.open_seconds)
  if (data?.open_seconds !== undefined && data?.open_seconds !== null && Number.isFinite(openSeconds)) {
    return Math.max(0, openSeconds)
  }
  return 10
}

function makeDoorSnapshot(data, previous) {
  if (data?.state !== 'open') return { state: 'closed', by: data?.by || null }
  const now = performance.now()
  const remainingAtReceive = getReportedDoorSeconds(data)
  if (remainingAtReceive <= 0) return { state: 'closed', by: data?.by || null }
  const reportedOpenSeconds = Number(data?.open_seconds)
  const capSeconds = Number.isFinite(reportedOpenSeconds) && reportedOpenSeconds > 0
    ? reportedOpenSeconds
    : remainingAtReceive
  return {
    state: 'open',
    by: data.by || null,
    remainingAtReceive,
    receivedAt: now,
    hardDeadline: previous?.state === 'open' ? previous.hardDeadline : now + (capSeconds + 5) * 1000,
  }
}

function getDoorRemainingSeconds(snapshot, now) {
  if (snapshot?.state !== 'open') return 0
  const fromResponse = snapshot.remainingAtReceive - (now - snapshot.receivedAt) / 1000
  const beforeHardLimit = (snapshot.hardDeadline - now) / 1000
  return Math.max(0, Math.ceil(Math.min(fromResponse, beforeHardLimit)))
}

function SystemStatus({ label, value, tone }) {
  return (
    <div className="dashboard-system-status">
      <span>{label}</span>
      <Badge tone={tone}>{value}</Badge>
    </div>
  )
}

export default function Dashboard() {
  const { connected, lastResult, cameraStatus, aiStatus, recording, doorState } = useDashboardSocket()
  const [logs, setLogs] = useState([])
  const [logsLoading, setLogsLoading] = useState(true)
  const [logsError, setLogsError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [streamState, setStreamState] = useState({ enabled: false, error: false })
  const [doorStatus, setDoorStatus] = useState(null)
  const doorStatusRef = useRef(null)
  const [doorLoading, setDoorLoading] = useState(true)
  const [doorError, setDoorError] = useState('')
  const [doorDialogOpen, setDoorDialogOpen] = useState(false)
  const [doorReason, setDoorReason] = useState('')
  const [doorSubmitting, setDoorSubmitting] = useState(false)
  const [doorActionError, setDoorActionError] = useState('')
  const [clockNow, setClockNow] = useState(() => performance.now())
  const doorEventVersionRef = useRef(0)
  const statusSyncPromiseRef = useRef(null)

  const loadLogs = useCallback(async () => {
    setLogsLoading(true)
    setLogsError('')
    try {
      const { data } = await api.get('/logs', { params: { from: startOfLocalDayIso(), limit: 200 } })
      setLogs(Array.isArray(data) ? data : [])
    } catch (error) {
      setLogsError(getApiErrorMessage(error, 'Không tải được hoạt động hôm nay.'))
    } finally {
      setLogsLoading(false)
    }
  }, [])

  useEffect(() => { void loadLogs() }, [lastResult, refreshKey, loadLogs])

  const applyDoorStatus = useCallback((data) => {
    const next = makeDoorSnapshot(data, doorStatusRef.current)
    doorStatusRef.current = next
    setDoorStatus(next)
    setClockNow(performance.now())
    return next
  }, [])

  const loadDoorStatus = useCallback(async ({ retryOnNetworkError = false, closeOnFailure = false } = {}) => {
    if (statusSyncPromiseRef.current) return statusSyncPromiseRef.current
    const requestVersion = doorEventVersionRef.current
    if (!doorStatusRef.current) setDoorLoading(true)
    setDoorError('')

    const request = (async () => {
      let lastError
      const maxAttempts = retryOnNetworkError ? 3 : 1
      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        try {
          // TODO(B17): mockGetDoorStatus mô phỏng door_service chỉ khi VITE_MOCK_ADMIN=1.
          const data = mockAdminEnabled
            ? await mockGetDoorStatus()
            : (await api.get('/door/status')).data
          if (requestVersion === doorEventVersionRef.current) {
            applyDoorStatus(data)
            setDoorError('')
          }
          return data
        } catch (error) {
          lastError = error
          const status = error?.response?.status
          const retryable = !error?.response || status >= 500
          if (attempt + 1 < maxAttempts && retryable) {
            await new Promise((resolve) => window.setTimeout(resolve, 1000))
            continue
          }
          break
        }
      }

      if (requestVersion === doorEventVersionRef.current) {
        if (closeOnFailure) applyDoorStatus({ state: 'closed' })
        else if (!doorStatusRef.current) setDoorError(getApiErrorMessage(lastError, 'Không tải được trạng thái cửa.'))
      }
      return null
    })()

    statusSyncPromiseRef.current = request
    try {
      return await request
    } finally {
      if (statusSyncPromiseRef.current === request) statusSyncPromiseRef.current = null
      setDoorLoading(false)
    }
  }, [applyDoorStatus])

  useEffect(() => { void loadDoorStatus() }, [loadDoorStatus])

  useEffect(() => {
    if (!doorState) return
    doorEventVersionRef.current += 1
    applyDoorStatus(doorState)
    setDoorError('')
  }, [doorState, applyDoorStatus])

  const wasConnectedRef = useRef(false)
  useEffect(() => {
    if (connected && !wasConnectedRef.current) void loadDoorStatus()
    wasConnectedRef.current = connected
  }, [connected, loadDoorStatus])

  const doorOpen = doorStatus?.state === 'open'
  const remainingSeconds = getDoorRemainingSeconds(doorStatus, clockNow)

  useEffect(() => {
    if (!doorOpen) return undefined
    const timer = window.setInterval(() => {
      const now = performance.now()
      setClockNow(now)
      const current = doorStatusRef.current
      if (current?.state !== 'open') return
      if (now >= current.hardDeadline) {
        applyDoorStatus({ state: 'closed' })
        return
      }
      if (getDoorRemainingSeconds(current, now) <= 0) {
        void loadDoorStatus({ retryOnNetworkError: true, closeOnFailure: true })
      }
    }, 200)
    return () => window.clearInterval(timer)
  }, [doorOpen, doorStatus, applyDoorStatus, loadDoorStatus])

  const handleStreamStatus = useCallback((status) => setStreamState(status), [])
  const todayLogs = useMemo(() => [...logs].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)), [logs])
  const grantedCount = todayLogs.filter((item) => item.decision === 'granted').length
  const deniedCount = todayLogs.filter((item) => item.decision === 'denied').length
  const latestAnnouncement = lastResult?.announcement
  const doorColumns = [
    { key: 'timestamp', label: 'Thời gian', render: (item) => formatTime(item.timestamp) },
    { key: 'name', label: 'Cư dân', render: (item) => item.name || item.user?.full_name || 'Không xác định' },
    { key: 'similarity', label: 'Độ giống', render: (item) => typeof item.similarity === 'number' ? item.similarity.toFixed(2) : '—' },
    { key: 'liveness', label: 'Chống giả mạo', render: (item) => item.liveness === true ? 'Đạt' : item.liveness === false ? 'Không đạt' : '—' },
    { key: 'decision', label: 'Kết quả', render: (item) => <Badge tone={item.decision === 'granted' ? 'success' : 'danger'}>{item.decision === 'granted' ? 'Cho phép' : 'Từ chối'}</Badge> },
    { key: 'reason', label: 'Lý do', render: (item) => getReasonLabel(item.reason) },
  ]

  const submitDoorOpen = async () => {
    setDoorSubmitting(true)
    setDoorActionError('')
    try {
      // TODO(B17): mockOpenDoor mô phỏng door_service chỉ khi VITE_MOCK_ADMIN=1.
      const data = mockAdminEnabled
        ? await mockOpenDoor(doorReason.trim())
        : (await api.post('/door/open', doorReason.trim() ? { reason: doorReason.trim() } : {})).data
      applyDoorStatus(data)
      setDoorDialogOpen(false)
      setDoorReason('')
    } catch (error) {
      const status = error?.response?.status
      if (status === 401 || status === 403) return
      if (!error?.response) {
        setDoorActionError('')
        window.dispatchEvent(new CustomEvent('app:toast', { detail: { tone: 'danger', message: 'Không mở được cửa' } }))
      } else {
        setDoorActionError(getApiErrorMessage(error, 'Không mở được cửa. Vui lòng thử lại.'))
      }
    } finally {
      setDoorSubmitting(false)
    }
  }

  const closeDoorDialog = useCallback(() => {
    if (!doorSubmitting) setDoorDialogOpen(false)
  }, [doorSubmitting])

  const cameraLabel = cameraStatus?.running ? 'Đang hoạt động' : cameraStatus ? 'Chưa sẵn sàng' : 'Đang kiểm tra'
  const aiLabel = aiStatus?.running ? 'Đang hoạt động' : aiStatus ? 'Đang dừng' : 'Đang kiểm tra'
  const streamLabel = streamState.error ? 'Lỗi tải' : streamState.enabled ? 'Đang xem' : 'Đang tắt'

  return (
    <main className="page dashboard-page">
      <section className="dashboard-welcome">
        <div>
          <p className="eyebrow">TRUNG TÂM AN NINH</p>
          <h2>Giám sát ra vào</h2>
          <p className="muted">Tình trạng hệ thống và hoạt động nhận diện trong hôm nay.</p>
        </div>
        <Button variant="secondary" onClick={() => setRefreshKey((key) => key + 1)} disabled={logsLoading}>Làm mới dữ liệu</Button>
      </section>

      <section className="dashboard-system-grid" aria-label="Trạng thái hệ thống">
        <SystemStatus label="WebSocket" value={connected ? 'Đã kết nối' : 'Đang kết nối lại'} tone={connected ? 'success' : 'warning'} />
        <SystemStatus label="Camera" value={cameraLabel} tone={cameraStatus?.running ? 'success' : 'warning'} />
        <SystemStatus label="AI" value={aiLabel} tone={aiStatus?.running ? 'success' : 'neutral'} />
        <SystemStatus label="Stream" value={streamLabel} tone={streamState.error ? 'danger' : streamState.enabled ? 'success' : 'neutral'} />
      </section>

      <section className="dashboard-metrics" aria-label="Số liệu trong ngày">
        <Card className="dashboard-metric"><span>Tổng lượt hôm nay</span><strong>{todayLogs.length}</strong><small>lượt ra vào được ghi nhận</small></Card>
        <Card className="dashboard-metric dashboard-metric--success"><span>Được cho phép</span><strong>{grantedCount}</strong><small>quyết định hợp lệ</small></Card>
        <Card className="dashboard-metric dashboard-metric--danger"><span>Bị từ chối</span><strong>{deniedCount}</strong><small>cần được lưu ý</small></Card>
      </section>

      <section className="dashboard-primary-grid">
        <Card as="article" className="dashboard-door-card">
          <div className="dashboard-card-heading">
            <div className="dashboard-card-icon"><DoorIcon /></div>
            <div><p className="eyebrow">ĐIỀU KHIỂN CỬA</p><h2>Cửa ra vào</h2></div>
            <div className="dashboard-door-badges">
              {!doorLoading && !doorError && <Badge tone={doorOpen ? 'warning' : 'success'}>{doorOpen ? 'Đang mở' : 'Đang đóng'}</Badge>}
              {!connected && <Badge className="dashboard-door-realtime-warning" tone="warning">Mất kết nối thời gian thực</Badge>}
            </div>
          </div>
          {doorLoading ? <p className="dashboard-door-copy">Đang tải trạng thái cửa…</p> : doorError ? (
            <ErrorState message={doorError} onRetry={() => void loadDoorStatus()} />
          ) : (
            <>
              <div className={`dashboard-door-indicator${doorOpen ? ' dashboard-door-indicator--open' : ''}`} aria-hidden="true"><span /></div>
              <p className="dashboard-door-copy">{doorOpen ? `Cửa đang mở · còn ${remainingSeconds} giây` : 'Cửa đang được khóa an toàn.'}</p>
              {doorOpen && doorStatus.by && <p className="dashboard-door-by">Mở bởi {doorStatus.by}</p>}
              {doorActionError && <ErrorState message={doorActionError} />}
              <Button className="dashboard-door-button" onClick={() => { setDoorActionError(''); setDoorDialogOpen(true) }} disabled={doorLoading || doorOpen}>
                {doorOpen ? `Đang mở · ${remainingSeconds} giây` : 'Mở cửa 10 giây'}
              </Button>
              {mockAdminEnabled && <small className="dashboard-demo-note">Chế độ mô phỏng, chưa kết nối khóa thật.</small>}
            </>
          )}
        </Card>

        <Card as="article" className="dashboard-latest-card">
          <div className="dashboard-card-heading"><div><p className="eyebrow">NHẬN DIỆN GẦN NHẤT</p><h2>Kết quả mới nhất</h2></div></div>
          {latestAnnouncement ? (
            <>
              <p className={`dashboard-announcement dashboard-announcement--${lastResult?.decision === 'granted' ? 'granted' : 'denied'}`}>{latestAnnouncement.display || 'Chưa có thông báo.'}</p>
              {latestAnnouncement.spoken && <p className="dashboard-spoken">Loa đọc: {latestAnnouncement.spoken}</p>}
              {recording && <div className="dashboard-recording"><div><strong>Đang ghi nhận khuôn mặt</strong><span>{recording.got ?? 0} khung · giữ {recording.kept ?? 0}</span></div><div className="progress-track"><span style={{ width: `${Math.max(0, Math.min(100, ((recording.t_ms || 0) / 3000) * 100))}%` }} /></div></div>}
            </>
          ) : <p className="dashboard-muted-state">Chưa có lượt nhận diện mới. Kết quả sẽ xuất hiện tại đây khi hệ thống ghi nhận người trước camera.</p>}
        </Card>
      </section>

      <section className="dashboard-secondary-grid">
        <Card as="article" className="dashboard-stream-card">
          <div className="dashboard-card-heading"><div><p className="eyebrow">CAMERA</p><h2>Xem trực tiếp</h2></div><Badge tone={streamState.enabled ? 'success' : 'neutral'}>{streamState.enabled ? 'Đang xem' : 'Tùy chọn'}</Badge></div>
          <LiveStream cameraStatus={cameraStatus} connected={connected} onStatusChange={handleStreamStatus} />
        </Card>
        <Card as="article" className="dashboard-activity-card">
          <div className="dashboard-card-heading"><div><p className="eyebrow">HÔM NAY</p><h2>Hoạt động gần đây</h2></div></div>
          <Table
            columns={doorColumns}
            rows={todayLogs.slice(0, 10)}
            rowKey={(item, index) => item.id ?? `${item.timestamp}-${index}`}
            loading={logsLoading}
            error={logsError}
            onRetry={() => setRefreshKey((key) => key + 1)}
            emptyTitle="Chưa có lượt ra vào"
            emptyDescription="Nhật ký sẽ xuất hiện sau khi hệ thống ghi nhận quyết định nhận diện."
            className="dashboard-activity-table"
          />
        </Card>
      </section>

      <Card as="section" className="dashboard-speaker-card">
        <div><p className="eyebrow">THIẾT BỊ</p><h2>Thông báo bằng loa</h2><p>Loa chưa được bật ở backend.</p></div>
        <Button variant="secondary" disabled title="Chức năng này chưa sẵn sàng ở backend">Tắt loa</Button>
      </Card>

      <ConfirmDialog
        open={doorDialogOpen}
        onClose={closeDoorDialog}
        onConfirm={() => void submitDoorOpen()}
        title="Xác nhận mở cửa"
        description="Cửa sẽ được mở trong tối đa 10 giây."
        confirmLabel="Mở cửa"
        cancelLabel="Hủy"
        loading={doorSubmitting}
        danger
      >
        <FormField id="door-open-reason" label="Lý do mở cửa" description="Không bắt buộc · tối đa 200 ký tự">
          <Input id="door-open-reason" description="Không bắt buộc · tối đa 200 ký tự" value={doorReason} onChange={(event) => setDoorReason(event.target.value)} maxLength={200} placeholder="Nhập lý do nếu cần" disabled={doorSubmitting} />
        </FormField>
        {doorActionError && <ErrorState message={doorActionError} />}
      </ConfirmDialog>
    </main>
  )
}
