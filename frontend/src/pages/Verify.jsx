// Agent 3 — Hiện stream (tùy chọn) và kết quả từng người theo sự kiện access_result (xác thực chạy tự động, không có nút chụp),
// khung mặt tính từ landmark, ô xem vùng cắt (chỉ mặt), câu loa đã đọc.
import { useState } from 'react'
import LiveStream from '../components/LiveStream.jsx'
import { useDashboardSocket } from '../hooks/useDashboardSocket.js'
import { mockEventsEnabled } from '../services/mock.js'
import { getReasonLabel } from '../services/reasons.js'

function getResidentName(result) {
  return result?.user?.full_name || result?.user?.name || result?.name || 'Không xác định'
}

export default function Verify() {
  const { connected, lastResult, cameraStatus } = useDashboardSocket()
  const [mockCount, setMockCount] = useState(0)
  const granted = lastResult?.decision === 'granted'

  const simulateAccessResult = () => {
    const allow = mockCount % 2 === 0
    const timestamp = new Date().toISOString()
    const announcement = allow
      ? {
          display: 'Nguyễn Văn An ở phòng A-1203 đã vào chung cư lúc 9 giờ 25 phút.',
          spoken: 'Nguyễn Văn An ở phòng A một hai không ba đã vào chung cư lúc chín giờ hai mươi lăm phút.',
          kind: 'granted',
        }
      : {
          display: 'Có người lạ đang ở ngoài chung cư, bảo vệ cần ra gấp.',
          spoken: 'Có người lạ đang ở ngoài chung cư, bảo vệ cần ra gấp.',
          kind: 'stranger',
        }
    const data = {
      user: allow ? { id: 1, user_code: 'USR000001', full_name: 'Nguyễn Văn An', apartment_number: 'A-1203' } : null,
      name: allow ? 'Nguyễn Văn An' : 'Không xác định',
      decision: allow ? 'granted' : 'denied',
      reason: allow ? 'ok' : 'not_matched',
      similarity: allow ? 0.94 : 0.23,
      liveness: true,
      timestamp,
      box: null,
      crop_b64: null,
      announcement,
    }
    // TODO B12: bỏ mô phỏng khi backend phát access_result thật.
    window.dispatchEvent(new CustomEvent('dashboard:mock-event', { detail: { event: 'access_result', data } }))
    setMockCount((count) => count + 1)
  }

  return (
    <main className="page verify-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">NHẬN DIỆN TỰ ĐỘNG</p>
          <h1>Xác thực</h1>
          <p className="muted">Kết quả xuất hiện khi hệ thống nhận diện khuôn mặt trước camera.</p>
        </div>
        {mockEventsEnabled && <button type="button" onClick={simulateAccessResult}>Mô phỏng sự kiện</button>}
      </header>

      <div className="verify-grid">
        <section className="panel verify-camera-panel">
          <div className="section-heading"><div><p className="eyebrow">CAMERA CỬA CHÍNH</p><h2>Luồng hình ảnh</h2></div></div>
          <LiveStream cameraStatus={cameraStatus} connected={connected} />
        </section>

        <section className="panel verify-result-panel" aria-live="polite">
          <div className="section-heading"><div><p className="eyebrow">KẾT QUẢ MỚI NHẤT</p><h2>Quyết định ra vào</h2></div></div>
          {lastResult ? (
            <div className={`verification-result ${granted ? 'verification-result--granted' : 'verification-result--denied'}`}>
              <span className={`result-chip ${granted ? 'result-chip--good' : 'result-chip--bad'}`}>{granted ? 'Cho phép' : 'Từ chối'}</span>
              <dl className="verification-details">
                <div><dt>Cư dân</dt><dd>{getResidentName(lastResult)}</dd></div>
                <div><dt>Độ giống</dt><dd>{typeof lastResult.similarity === 'number' ? lastResult.similarity.toFixed(2) : '—'}</dd></div>
                <div><dt>Chống giả mạo</dt><dd>{lastResult.liveness === true ? 'Đạt' : lastResult.liveness === false ? 'Không đạt' : '—'}</dd></div>
                <div><dt>Lý do</dt><dd>{getReasonLabel(lastResult.reason)}</dd></div>
              </dl>
            </div>
          ) : (
            <div className="verify-waiting" role="status">
              <span className={`status-chip ${connected ? 'status-chip--good' : 'status-chip--warning'}`}>{connected ? 'Đã kết nối' : 'Đang kết nối lại'}</span>
              <p>{connected ? 'Đang chờ sự kiện xác thực từ camera…' : 'Đang kết nối hệ thống xác thực…'}</p>
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
