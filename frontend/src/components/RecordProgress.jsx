// Agent 3 — Thanh tiến độ 3 giây và số khung đã thu
export default function RecordProgress({ elapsedMs = 0, recording }) {
  const duration = 3000
  const currentMs = Math.max(0, Math.min(duration, recording?.t_ms ?? elapsedMs))
  const percent = Math.round((currentMs / duration) * 100)

  return (
    <section className="record-progress" aria-live="polite">
      <div className="record-progress__meta">
        <strong>Đang quay, giữ yên mặt · {((duration - currentMs) / 1000).toFixed(1)} giây</strong>
        <span>Thu được {recording?.got ?? 0} khung · giữ lại {recording?.kept ?? 0}</span>
      </div>
      <div className="progress-track" role="progressbar" aria-label="Tiến độ ghi hình" aria-valuemin="0" aria-valuemax="100" aria-valuenow={percent}>
        <span style={{ width: `${percent}%` }} />
      </div>
    </section>
  )
}
