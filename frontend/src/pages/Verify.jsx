// Agent 3 — Hiện stream (tùy chọn) và kết quả từng người theo sự kiện access_result (xác thực chạy tự động, không có nút chụp),
// khung mặt tính từ landmark, ô xem vùng cắt (chỉ mặt), câu loa đã đọc.
import { useState } from 'react'
import LiveStream from '../components/LiveStream.jsx'
import { useDashboardSocket } from '../hooks/useDashboardSocket.js'
import FaceBox from '../components/FaceBox.jsx'
import DoorStatus from '../components/DoorStatus.jsx'
import { mockEventsEnabled } from '../services/mock.js'
import { getReasonLabel } from '../services/reasons.js'

function getResidentName(result) {
  return result?.user?.full_name || result?.user?.name || result?.name || 'Không xác định'
}

function formatEventTime(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString('vi-VN')
}

export default function Verify() {
  const { connected, lastResult, cameraStatus, doorState } = useDashboardSocket()
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
      box: {
        bbox: [200, 60, 440, 420],
        landmarks: [[260, 175], [380, 175], [320, 245], [275, 320], [365, 320]],
      },
      crop_b64: window.btoa('<svg xmlns="http://www.w3.org/2000/svg" width="112" height="112" viewBox="0 0 112 112"><rect width="112" height="112" fill="#e5eff1"/><ellipse cx="56" cy="49" rx="28" ry="34" fill="#e8bd9d"/><path d="M28 46c0-31 56-31 56 0v-9c0-20-56-20-56 0z" fill="#273a45"/><circle cx="46" cy="48" r="3" fill="#273a45"/><circle cx="66" cy="48" r="3" fill="#273a45"/><path d="M47 65q9 7 18 0" fill="none" stroke="#7d4c3d" stroke-width="2" stroke-linecap="round"/><path d="M18 112c4-25 18-34 38-34s34 9 38 34" fill="#167c87"/></svg>'),
      crop_mime_type: 'image/svg+xml',
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
          <LiveStream
            cameraStatus={cameraStatus}
            connected={connected}
            overlay={lastResult?.box ? <FaceBox box={lastResult.box} width={cameraStatus?.width} height={cameraStatus?.height} /> : null}
          />
          <div className="crop-preview">
            {lastResult?.crop_b64 ? (
              <img
                src={lastResult.crop_b64.startsWith('data:') ? lastResult.crop_b64 : `data:${lastResult.crop_mime_type || 'image/jpeg'};base64,${lastResult.crop_b64}`}
                alt="Vùng đưa vào nhận diện, chỉ khuôn mặt"
              />
            ) : (
              <div className="crop-preview__empty">Chờ vùng cắt từ sự kiện nhận diện</div>
            )}
            <p>vùng đưa vào nhận diện (chỉ mặt)</p>
          </div>
        </section>

        <section className="panel verify-result-panel" aria-live="polite">
          <div className="section-heading"><div><p className="eyebrow">KẾT QUẢ MỚI NHẤT</p><h2>Quyết định ra vào</h2></div></div>
          {lastResult ? (
            <>
              <div className={`verification-result ${granted ? 'verification-result--granted' : 'verification-result--denied'}`}>
                <span className={`result-chip ${granted ? 'result-chip--good' : 'result-chip--bad'}`}>{granted ? 'Cho phép' : 'Từ chối'}</span>
                <dl className="verification-details">
                  <div><dt>Cư dân</dt><dd>{getResidentName(lastResult)}</dd></div>
                  <div><dt>Độ giống</dt><dd>{typeof lastResult.similarity === 'number' ? lastResult.similarity.toFixed(2) : '—'}</dd></div>
                  <div><dt>Chống giả mạo</dt><dd>{lastResult.liveness === true ? 'Đạt' : lastResult.liveness === false ? 'Không đạt' : '—'}</dd></div>
                  <div><dt>Lý do</dt><dd>{getReasonLabel(lastResult.reason)}</dd></div>
                </dl>
              </div>
              {lastResult.announcement?.display && (
                <section className={`announcement-card ${granted ? 'announcement-card--granted' : 'announcement-card--denied'}`}>
                  <div className="announcement-card__heading"><strong>Thông báo</strong><time dateTime={lastResult.timestamp}>{formatEventTime(lastResult.timestamp)}</time></div>
                  <p className="announcement-card__display">{lastResult.announcement.display}</p>
                  {lastResult.announcement.spoken && <p className="announcement-card__spoken">Loa đọc: {lastResult.announcement.spoken}</p>}
                </section>
              )}
            </>
          ) : (
            <div className="verify-waiting" role="status">
              <span className={`status-chip ${connected ? 'status-chip--good' : 'status-chip--warning'}`}>{connected ? 'Đã kết nối' : 'Đang kết nối lại'}</span>
              <p>{connected ? 'Đang chờ sự kiện xác thực từ camera…' : 'Đang kết nối hệ thống xác thực…'}</p>
            </div>
          )}
        </section>
      </div>
      <DoorStatus doorState={doorState} />
    </main>
  )
}
