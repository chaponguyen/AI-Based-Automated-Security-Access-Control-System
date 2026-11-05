// Agent 3 — Điều khiển cửa: Đã khóa / đang mở + đếm ngược
// Đếm lùi bằng performance.now(): không phụ thuộc múi giờ hay đồng hồ tuyệt đối.
// Khi nhận remaining_seconds từ POST /open, GET /status hoặc WS door_state,
// lưu thời điểm nhận bằng performance.now() rồi tính còn lại = remaining - (now - receivedAt).
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, getApiErrorMessage } from '../services/api.js'

/**
 * Tạo snapshot đếm lùi từ payload door (open, door_state hoặc status).
 * @param {object} payload  - phải có remaining_seconds (ưu tiên) hoặc open_seconds
 * @param {number} receivedAt - performance.now() tại thời điểm nhận (ms)
 */
function makeCountdown(payload, receivedAt) {
  if (!payload || payload.state !== 'open') return null
  // Ưu tiên remaining_seconds (backend B16+), fallback open_seconds
  const secs = typeof payload.remaining_seconds === 'number'
    ? payload.remaining_seconds
    : typeof payload.open_seconds === 'number'
      ? payload.open_seconds
      : 10
  return { total: secs, receivedAt }
}

/**
 * Tính số giây còn lại từ snapshot đếm lùi.
 */
function calcRemaining(countdown) {
  if (!countdown) return 0
  const elapsed = (performance.now() - countdown.receivedAt) / 1000
  return Math.max(0, countdown.total - elapsed)
}

export default function DoorStatus({ doorState }) {
  const [opening, setOpening] = useState(false)  // đang gọi POST
  const [error, setError] = useState('')
  const [displaySecs, setDisplaySecs] = useState(0)
  const countdownRef = useRef(null)  // { total, receivedAt }
  const rafRef = useRef(null)
  const pollingRef = useRef(null)

  // Khi doorState thay đổi (WS), cập nhật countdown
  useEffect(() => {
    if (!doorState) return
    if (doorState.state === 'open') {
      const receivedAt = typeof doorState._receivedAt === 'number'
        ? doorState._receivedAt
        : performance.now()
      countdownRef.current = makeCountdown(doorState, receivedAt)
    } else {
      countdownRef.current = null
      setDisplaySecs(0)
      setOpening(false)
      clearPolling()
    }
  }, [doorState])

  // Vòng lặp requestAnimationFrame để cập nhật màn hình mỗi khung
  useEffect(() => {
    const tick = () => {
      if (countdownRef.current) {
        const rem = calcRemaining(countdownRef.current)
        setDisplaySecs(Math.ceil(rem))
        if (rem <= 0) {
          // Hết giờ: poll status để chốt trạng thái (WS có thể chậm 1-2s)
          countdownRef.current = null
          setDisplaySecs(0)
          startPolling()
        }
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [])

  const clearPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const startPolling = useCallback(() => {
    clearPolling()
    // Poll tối đa 5 lần (mỗi 500ms) sau khi đếm về 0
    let attempts = 0
    pollingRef.current = setInterval(async () => {
      attempts++
      try {
        const { data } = await api.get('/door/status')
        if (data.state === 'closed') {
          countdownRef.current = null
          setDisplaySecs(0)
          setOpening(false)
          clearPolling()
        } else if (data.state === 'open') {
          const snap = makeCountdown(data, performance.now())
          if (snap) {
            countdownRef.current = snap
            clearPolling()
          }
        }
      } catch {
        // Giữ trạng thái gần nhất; WS sẽ đồng bộ
      }
      if (attempts >= 10) clearPolling()
    }, 500)
  }, [clearPolling])

  // Cleanup polling khi unmount
  useEffect(() => () => clearPolling(), [clearPolling])

  const handleOpen = useCallback(async () => {
    if (opening) return
    setOpening(true)
    setError('')
    try {
      const { data } = await api.post('/door/open')
      // data: { state, open_seconds, until, already_open, remaining_seconds? }
      const receivedAt = performance.now()
      if (data.state === 'open') {
        const snap = makeCountdown(
          { ...data, remaining_seconds: data.remaining_seconds ?? data.open_seconds },
          receivedAt
        )
        countdownRef.current = snap
      }
      // Nếu already_open: giữ nguyên countdown hiện tại (không reset)
      if (data.already_open && !countdownRef.current) {
        // Không có thông tin đủ, gọi thêm GET /status
        try {
          const { data: st } = await api.get('/door/status')
          if (st.state === 'open') {
            countdownRef.current = makeCountdown(st, performance.now())
          }
        } catch { /* ignore */ }
      }
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể mở cửa. Thử lại sau.'))
      setOpening(false)
    }
  }, [opening])

  // Xác định trạng thái hiển thị
  const isOpen = countdownRef.current !== null || (doorState?.state === 'open')
  const isOpening = opening && !isOpen

  return (
    <div className="door-status">
      <div className="door-status__state" aria-live="polite">
        {isOpen ? (
          <>
            <span className="door-badge door-badge--open">🔓 Đang mở</span>
            <span className="door-countdown">
              {displaySecs > 0 ? `· còn ${displaySecs} giây` : '· đang đóng…'}
            </span>
          </>
        ) : (
          <span className="door-badge door-badge--closed">🔒 Đã khóa</span>
        )}
      </div>

      {error && (
        <p className="door-status__error" role="alert">{error}</p>
      )}

      <button
        id="btn-door-open"
        type="button"
        className="button button--primary door-status__btn"
        onClick={handleOpen}
        disabled={isOpen || isOpening}
        aria-busy={isOpening}
      >
        {isOpening ? 'Đang mở…' : isOpen ? `Đang mở (${displaySecs}s)` : 'Mở cửa'}
      </button>

      {doorState?.by && isOpen && (
        <p className="door-status__by muted">Mở bởi: {doorState.by}</p>
      )}
    </div>
  )
}
