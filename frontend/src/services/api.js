// Agent 3 — gọi REST theo docs/context/API_CONTRACT.md
import axios from 'axios'

export const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export const api = axios.create({ baseURL: `${API_BASE_URL}/api`, withCredentials: true })

api.interceptors.response.use((response) => response, (error) => {
  const status = error?.response?.status
  const url = error?.config?.url || ''
  if (status === 401 && !/\/auth\/(login|me)(?:\?|$)/.test(url)) {
    window.dispatchEvent(new CustomEvent('auth:expired'))
  } else if (status === 403) {
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { tone: 'danger', message: 'Bạn không có quyền thực hiện thao tác này' } }))
  }
  return Promise.reject(error)
})

export function getApiErrorMessage(error, fallback = 'Không tải được dữ liệu. Vui lòng thử lại.') {
  if (!error?.response) return 'Không thể kết nối backend. Hãy kiểm tra kết nối rồi thử lại.'
  if (error.response.status === 404 || error.response.status === 405) {
    return 'Chức năng này chưa sẵn sàng ở backend.'
  }
  return fallback
}
