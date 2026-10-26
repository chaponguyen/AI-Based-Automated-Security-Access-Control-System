// Agent 3 — Hiện stream (tùy chọn) và kết quả từng người theo sự kiện access_result (xác thực chạy tự động, không có nút chụp),
// khung mặt tính từ landmark, ô xem vùng cắt (chỉ mặt), câu loa đã đọc.
import LiveStream from '../components/LiveStream.jsx'
import { useDashboardSocket } from '../hooks/useDashboardSocket.js'
import FaceBox from '../components/FaceBox.jsx'
import DoorStatus from '../components/DoorStatus.jsx'
import Badge from '../components/ui/Badge.jsx'
import Card from '../components/ui/Card.jsx'
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
  const granted = lastResult?.decision === 'granted'

  return (
    <main className="page verify-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">NHẬN DIỆN TỰ ĐỘNG</p>
          <h1>Xác thực</h1>
          <p className="muted">Kết quả xuất hiện khi hệ thống nhận diện khuôn mặt trước camera.</p>
        </div>
      </header>

      <div className="verify-grid">
        <Card as="section" className="verify-camera-panel">
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
        </Card>

        <Card as="section" className="verify-result-panel" aria-live="polite">
          <div className="section-heading"><div><p className="eyebrow">KẾT QUẢ MỚI NHẤT</p><h2>Quyết định ra vào</h2></div></div>
          {lastResult ? (
            <>
              <div className={`verification-result ${granted ? 'verification-result--granted' : 'verification-result--denied'}`}>
                <Badge tone={granted ? 'success' : 'danger'}>{granted ? 'Cho phép' : 'Từ chối'}</Badge>
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
              <Badge tone={connected ? 'success' : 'warning'}>{connected ? 'Đã kết nối' : 'Đang kết nối lại'}</Badge>
              <p>{connected ? 'Đang chờ sự kiện xác thực từ camera…' : 'Đang kết nối hệ thống xác thực…'}</p>
            </div>
          )}
        </Card>
      </div>
      <DoorStatus doorState={doorState} />
    </main>
  )
}
