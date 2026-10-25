// Agent 3 — gọi REST theo docs/context/API_CONTRACT.md
import axios from 'axios'

export const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export const api = axios.create({ baseURL: `${API_BASE_URL}/api` })
