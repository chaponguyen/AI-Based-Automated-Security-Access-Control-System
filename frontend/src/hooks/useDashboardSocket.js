// Agent 3 — kết nối /ws/dashboard, tự nối lại; trả {connected, lastResult, cameraStatus, aiStatus, recording}
// KHÔNG dùng getUserMedia: camera do backend giữ.
import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL, api } from '../services/api.js'

const reconnectDelay = (attempt) => Math.min(attempt * 1000, 10000)

export function useDashboardSocket() {
  const [connected, setConnected] = useState(false)
  const [lastResult, setLastResult] = useState(null)
  const [cameraStatus, setCameraStatus] = useState(null)
  const [aiStatus, setAiStatus] = useState(null)
  const [recording, setRecording] = useState(null)
  const [doorState, setDoorState] = useState(null)
  const connectedRef = useRef(false)

  useEffect(() => {
    let stopped = false
    let socket = null
    let reconnectTimer = null
    let attempt = 0

    const socketUrl = new URL(`${API_BASE_URL}/ws/dashboard`)
    socketUrl.protocol = socketUrl.protocol === 'https:' ? 'wss:' : 'ws:'

    const connect = () => {
      if (stopped) return

      let currentSocket
      try {
        currentSocket = new WebSocket(socketUrl.href)
      } catch {
        reconnect()
        return
      }

      socket = currentSocket
      currentSocket.onopen = () => {
        if (stopped || socket !== currentSocket) return
        connectedRef.current = true
        setConnected(true)
      }
      currentSocket.onmessage = (message) => {
        if (stopped || socket !== currentSocket) return
        try {
          const event = JSON.parse(message.data)
          if (!event || typeof event !== 'object' || !event.data || typeof event.data !== 'object') return

          switch (event.event) {
            case 'camera_status':
              setCameraStatus(event.data)
              break
            case 'access_result':
              setLastResult(event.data)
              break
            case 'ai_status':
              setAiStatus(event.data)
              break
            case 'record_progress':
              setRecording(event.data)
              break
            case 'door_state':
              setDoorState({ ...event.data, _receivedAt: performance.now() })
              break
            default:
              // Bỏ qua ping và các event chưa được giao diện sử dụng.
              break
          }
        } catch {
          // Bỏ qua gói lỗi định dạng để giao diện không bị dừng.
        }
      }
      currentSocket.onerror = () => currentSocket.close()
      currentSocket.onclose = () => {
        if (socket !== currentSocket) return
        socket = null
        connectedRef.current = false
        setConnected(false)
        reconnect()
      }
    }

    const handleMockEvent = (customEvent) => {
      const { event, data } = customEvent.detail || {}
      if (!data || typeof data !== 'object') return
      switch (event) {
        case 'access_result':
          setLastResult(data)
          break
        case 'camera_status':
          setCameraStatus(data)
          break
        case 'ai_status':
          setAiStatus(data)
          break
        case 'record_progress':
          setRecording(data)
          break
        case 'door_state':
          setDoorState({ ...data, _receivedAt: performance.now() })
          break
        default:
          break
      }
    }

    const reconnect = () => {
      if (stopped || reconnectTimer !== null) return
      attempt += 1
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null
        connect()
      }, reconnectDelay(attempt))
    }

    connect()
    window.addEventListener('dashboard:mock-event', handleMockEvent)
    const pollTimer = window.setInterval(async () => {
      if (stopped || connectedRef.current) return
      try {
        const response = await api.get('/camera/status')
        if (!stopped && !connectedRef.current) setCameraStatus(response.data)
      } catch {
        // Giữ trạng thái gần nhất; WebSocket và polling sẽ tự thử lại.
      }
    }, 2000)

    return () => {
      stopped = true
      connectedRef.current = false
      window.removeEventListener('dashboard:mock-event', handleMockEvent)
      window.clearInterval(pollTimer)
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      if (socket) {
        socket.onclose = null
        socket.close()
      }
    }
  }, [])

  return { connected, lastResult, cameraStatus, aiStatus, recording, doorState }
}
