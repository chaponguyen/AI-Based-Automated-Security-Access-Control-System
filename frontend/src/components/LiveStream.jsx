// Agent 3 — <img src="/api/stream"> chỉ khi người dùng bật; mặc định tắt; tắt hoặc rời trang thì src=""
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '../services/api.js'

export default function LiveStream({ cameraStatus, connected, onStatusChange }) {
  const [enabled, setEnabled] = useState(false)
  const [streamTimestamp, setStreamTimestamp] = useState(0)
  const [retrying, setRetrying] = useState(false)
  const imageRef = useRef(null)
  const enabledRef = useRef(false)
  const retryTimerRef = useRef(null)
  const retryAttemptRef = useRef(0)
  const streamTimestampRef = useRef(0)
  const previousConnectedRef = useRef(Boolean(connected))
  const previousCameraRunningRef = useRef(cameraStatus?.running)
  const cameraUnavailable = cameraStatus?.running === false

  useEffect(() => {
    onStatusChange?.({ enabled, error: false, retrying })
  }, [enabled, retrying, onStatusChange])

  const closeImageRequest = (image = imageRef.current) => {
    if (!image) return
    image.src = ''
    image.removeAttribute('src')
    if (imageRef.current === image) imageRef.current = null
  }

  const clearRetryTimer = () => {
    if (retryTimerRef.current !== null) {
      window.clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }
  }

  const changeStreamUrl = () => {
    const nextTimestamp = Math.max(Date.now(), streamTimestampRef.current + 1)
    streamTimestampRef.current = nextTimestamp
    setStreamTimestamp(nextTimestamp)
  }

  const restartNow = () => {
    if (!enabledRef.current || cameraUnavailable) return
    clearRetryTimer()
    retryAttemptRef.current = 0
    closeImageRequest()
    setRetrying(true)
    changeStreamUrl()
  }

  const scheduleRetry = (failedTimestamp) => {
    if (!enabledRef.current || cameraUnavailable || failedTimestamp !== streamTimestampRef.current) return
    if (retryTimerRef.current !== null) return

    setRetrying(true)
    const delayMs = Math.min(1000 * (2 ** retryAttemptRef.current), 10000)
    retryAttemptRef.current += 1
    retryTimerRef.current = window.setTimeout(() => {
      retryTimerRef.current = null
      if (!enabledRef.current || cameraUnavailable) return
      closeImageRequest()
      changeStreamUrl()
    }, delayMs)
  }

  const startStream = () => {
    clearRetryTimer()
    retryAttemptRef.current = 0
    enabledRef.current = true
    setEnabled(true)
    setRetrying(cameraUnavailable)
    if (!cameraUnavailable) changeStreamUrl()
  }

  const stopStream = () => {
    enabledRef.current = false
    clearRetryTimer()
    retryAttemptRef.current = 0
    closeImageRequest()
    setRetrying(false)
    setEnabled(false)
  }

  useEffect(() => {
    const wasConnected = previousConnectedRef.current
    const wasCameraRunning = previousCameraRunningRef.current
    const websocketRestored = Boolean(connected) && !wasConnected
    const cameraRestored = cameraStatus?.running === true && wasCameraRunning === false
    previousConnectedRef.current = Boolean(connected)
    if (cameraStatus?.running !== undefined) previousCameraRunningRef.current = cameraStatus.running

    if (enabledRef.current && cameraStatus?.running === false) {
      clearRetryTimer()
      closeImageRequest()
      setRetrying(true)
      return
    }
    if (enabledRef.current && (websocketRestored || cameraRestored)) restartNow()
  }, [connected, cameraStatus?.running])

  useLayoutEffect(() => () => {
    enabledRef.current = false
    clearRetryTimer()
    retryAttemptRef.current = 0
    closeImageRequest()
  }, [])

  const streamUrl = `${API_BASE_URL}/api/stream?t=${streamTimestamp}`
  const showImage = enabled && !cameraUnavailable && streamTimestamp > 0

  return (
    <section className="live-stream" aria-label="Camera trực tiếp">
      <div className="live-stream__controls">
        <button type="button" onClick={enabled ? stopStream : startStream}>
          {enabled ? 'Tắt xem trực tiếp' : 'Xem trực tiếp'}
        </button>
      </div>

      {showImage && (
        <div className="live-stream__frame">
          <img
            ref={imageRef}
            className="live-stream__image"
            src={streamUrl}
            alt="Hình ảnh camera trực tiếp"
            onLoad={() => setRetrying(false)}
            onError={() => scheduleRetry(streamTimestamp)}
          />
          {retrying && <p className="live-stream__retry" role="status">Đang kết nối lại camera...</p>}
        </div>
      )}

      {!enabled && <p>Stream đang tắt, AI vẫn chạy.</p>}
      {enabled && cameraUnavailable && <p>Camera chưa sẵn sàng.</p>}
      {enabled && cameraUnavailable && retrying && <p role="status">Đang kết nối lại camera...</p>}
    </section>
  )
}
