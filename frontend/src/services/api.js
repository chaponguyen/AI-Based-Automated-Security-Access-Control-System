// Agent 3 — gọi REST theo docs/context/API_CONTRACT.md
import axios from 'axios'
export const api = axios.create({ baseURL: 'http://localhost:8000/api' })
