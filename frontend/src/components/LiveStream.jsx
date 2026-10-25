// Agent 3 — <img src="/api/stream"> chỉ khi người dùng bật; mặc định tắt; tắt hoặc rời trang thì src=""
import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '../services/api.js'

export default function LiveStream({ cameraStatus }) {
  const [enabled, setEnabled] = useState(false)
  const [streamKey, setStreamKey] = useState(0)
  const [loadError, setLoadError] = useState(false)
  const imageRef = useRef(null)
  const cameraUnavailable = cameraStatus?.running === false

  useEffect(() => {
    const activeImage = imageRef.current
    return () => {
      if (activeImage) {
        activeImage.src = ''
        activeImage.removeAttribute('src')
      }
    }
  }, [enabled, streamKey, cameraUnavailable])

  const stopStream = () => {
    if (imageRef.current) {
      imageRef.current.src = ''
      imageRef.current.removeAttribute('src')
    }
    setLoadError(false)
    setEnabled(false)
  }

  const startStream = () => {
    setLoadError(false)
    setStreamKey((key) => key + 1)
    setEnabled(true)
  }

  const streamUrl = `${API_BASE_URL}/api/stream?t=${streamKey}`

  return (
    <section className="live-stream" aria-label="Camera trực tiếp">
      <div className="live-stream__controls">
        <button type="button" onClick={enabled ? stopStream : startStream}>
          {enabled ? 'Tắt xem trực tiếp' : 'Xem trực tiếp'}
        </button>
        {enabled && loadError && (
          <button type="button" onClick={startStream}>Thử lại</button>
        )}
      </div>

      {enabled && !cameraUnavailable && !loadError && (
        <img
          ref={imageRef}
          className="live-stream__image"
          src={streamUrl}
          alt="Hình ảnh camera trực tiếp"
          onError={() => setLoadError(true)}
        />
      )}

      {!enabled && <p>Stream đang tắt, AI vẫn chạy.</p>}
      {enabled && cameraUnavailable && <p>Camera chưa sẵn sàng.</p>}
      {enabled && loadError && <p role="alert">Không tải được luồng camera. Hãy thử lại.</p>}
    </section>
  )
}
