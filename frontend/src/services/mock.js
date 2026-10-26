// Các cờ mock chỉ bật khi Vite nhận giá trị "1" trong file môi trường.
export const mockRegisterEnabled = import.meta.env.VITE_MOCK_REGISTER === '1'
export const mockEventsEnabled = import.meta.env.VITE_MOCK_EVENTS === '1'
// Chỉ bật tài khoản giả trong môi trường demo; không dùng các thông tin này khi gọi backend thật.
export const mockAuthEnabled = import.meta.env.VITE_MOCK_AUTH === '1'
// TODO(B17): bỏ mock quản trị sau khi backend B15/B16 sẵn sàng.
export const mockAdminEnabled = import.meta.env.VITE_MOCK_ADMIN === '1'
const configuredPrepareSeconds = Number(import.meta.env.VITE_REGISTER_PREPARE_SECONDS)
export const PREPARE_SECONDS = Number.isFinite(configuredPrepareSeconds) && configuredPrepareSeconds >= 1
  ? Math.floor(configuredPrepareSeconds)
  : 5

let mockResidentId = 900000
const mockDeletedResidentIds = new Set()
const mockDeletedLogIds = new Set()
const mockDeletedLogRanges = []
let mockDoorUntil = 0
let mockDoorTimer = null
let mockSessionUser = null

// TODO(B17): bỏ phiên giả sau khi API đăng nhập B15 sẵn sàng.
export async function mockLogin(username, password) {
  if (!mockAuthEnabled) throw new Error('Mock xác thực đang tắt')
  if (username === 'locked') {
    const error = new Error('Tài khoản đang tạm khóa')
    error.response = { status: 423, data: { reason: 'locked', retry_after_s: 30 } }
    throw error
  }
  const accounts = {
    manager: { password: 'manager123', user: { id: 1, username: 'manager', full_name: 'Quản lý demo', role: 'manager' } },
    security: { password: 'security123', user: { id: 2, username: 'security', full_name: 'Nhân viên an ninh demo', role: 'security' } },
  }
  const account = accounts[String(username || '').trim()]
  if (!account || account.password !== password) {
    const error = new Error('Sai tên đăng nhập hoặc mật khẩu')
    error.response = { status: 401, data: { reason: 'invalid_credentials' } }
    throw error
  }
  mockSessionUser = account.user
  return { ...mockSessionUser }
}

export async function mockGetAuthMe() {
  return mockSessionUser ? { ...mockSessionUser } : null
}

export async function mockLogout() {
  mockSessionUser = null
  return { ok: true }
}

function dispatchMockDoorState(data) {
  window.dispatchEvent(new CustomEvent('dashboard:mock-event', { detail: { event: 'door_state', data } }))
}

// TODO(B17): thay mock trạng thái cửa bằng GET /api/door/status sau khi B16 sẵn sàng.
export async function mockGetDoorStatus() {
  const isOpen = mockDoorUntil > Date.now()
  return {
    state: isOpen ? 'open' : 'closed',
    until: isOpen ? new Date(mockDoorUntil).toISOString() : null,
    by: isOpen ? 'Nhân viên mô phỏng' : null,
  }
}

// TODO(B17): thay mock mở cửa bằng POST /api/door/open sau khi B16 sẵn sàng.
export async function mockOpenDoor(reason = '') {
  if (mockDoorUntil > Date.now()) {
    return { ...(await mockGetDoorStatus()), open_seconds: Math.ceil((mockDoorUntil - Date.now()) / 1000), already_open: true }
  }

  if (mockDoorTimer !== null) window.clearTimeout(mockDoorTimer)
  mockDoorUntil = Date.now() + 10000
  const openState = {
    state: 'open',
    until: new Date(mockDoorUntil).toISOString(),
    open_seconds: 10,
    by: 'Nhân viên mô phỏng',
    reason: reason || null,
    already_open: false,
  }
  dispatchMockDoorState(openState)
  mockDoorTimer = window.setTimeout(() => {
    mockDoorUntil = 0
    mockDoorTimer = null
    dispatchMockDoorState({ state: 'closed', until: null, open_seconds: 0, by: null, reason: null })
  }, 10000)
  return openState
}

export async function mockDeleteResident(id, resident = {}) {
  // TODO(B17): thay bằng DELETE /api/residents/{id} khi backend quản trị sẵn sàng.
  mockDeletedResidentIds.add(Number(id))
  return {
    ok: true,
    deleted: {
      id: Number(id),
      user_code: resident.user_code || `USR${String(id).padStart(6, '0')}`,
      full_name: resident.full_name || '',
    },
  }
}

export function mockIsResidentDeleted(id) {
  return mockDeletedResidentIds.has(Number(id))
}

// TODO(B17): thay bằng POST /api/logs/delete khi backend quản trị sẵn sàng.
export async function mockDeleteLogs(payload = {}, expectedCount = 0) {
  if (Array.isArray(payload.ids)) {
    payload.ids.forEach((id) => mockDeletedLogIds.add(String(id)))
  } else if (payload.from && payload.to) {
    mockDeletedLogRanges.push({ from: new Date(payload.from).getTime(), to: new Date(payload.to).getTime() })
  }
  return { deleted: expectedCount }
}

export function mockFilterDeletedLogs(rows = []) {
  return rows.filter((row) => {
    if (mockDeletedLogIds.has(String(row.id))) return false
    const timestamp = new Date(row.timestamp).getTime()
    return !mockDeletedLogRanges.some((range) => timestamp >= range.from && timestamp <= range.to)
  })
}

const mockAuditEntries = [
  { id: 'audit-1', timestamp: '2026-10-26T08:45:00Z', staff_username: 'manager-demo', action: 'door.open', target_type: 'door', target_id: null, detail: 'Mở cửa 10 giây (mô phỏng)' },
  { id: 'audit-2', timestamp: '2026-10-26T08:30:00Z', staff_username: 'manager-demo', action: 'resident.status', target_type: 'resident', target_id: 8, detail: 'Đổi quyền cư dân (mô phỏng)' },
  { id: 'audit-3', timestamp: '2026-10-26T08:10:00Z', staff_username: 'manager-demo', action: 'staff.create', target_type: 'staff', target_id: 3, detail: 'Tạo tài khoản nhân viên (mô phỏng)' },
]

// TODO(B17): bỏ dữ liệu audit giả sau khi backend B16 sẵn sàng.
export async function mockGetAudit({ limit = 200, action = '', q = '' } = {}) {
  const query = String(q).trim().toLocaleLowerCase('vi')
  return mockAuditEntries
    .filter((entry) => (!action || entry.action === action) && (!query || `${entry.staff_username} ${entry.action} ${entry.target_type} ${entry.detail}`.toLocaleLowerCase('vi').includes(query)))
    .slice(0, Number(limit) || 200)
}

export async function mockRegistrationPrecheck(fullName) {
  await Promise.resolve()
  const name = String(fullName || '').trim()
  if (!name.startsWith('DUP_')) return { state: 'new', exists: false, user: null, similarity: null, box: null }

  return {
    state: 'exists',
    exists: true,
    user: {
      id: 1,
      user_code: 'USR000001',
      full_name: name,
      apartment_number: 'A-1203',
      status: 'active',
    },
    similarity: 0.98,
    box: null,
  }
}

export async function mockRegisterResident({ full_name, age, apartment_number }) {
  for (let elapsed = 250; elapsed <= 3000; elapsed += 250) {
    await new Promise((resolve) => window.setTimeout(resolve, 250))
    window.dispatchEvent(new CustomEvent('dashboard:mock-event', {
      detail: {
        event: 'record_progress',
        data: { t_ms: elapsed, got: Math.round(elapsed / 100), kept: Math.min(20, Math.round(elapsed / 120)) },
      },
    }))
  }

  const name = full_name.trim()
  if (name.toUpperCase().startsWith('LOI422')) {
    const error = new Error('Mock registration quality failure')
    error.response = { status: 422, data: { reason: 'not_enough_quality_frames', good: 9, required: 15 } }
    throw error
  }
  if (name.toUpperCase().startsWith('LOI409')) {
    const error = new Error('Mock registration already in progress')
    error.response = { status: 409, data: { reason: 'registration_in_progress' } }
    throw error
  }

  mockResidentId += 1
  return {
    status: 201,
    data: {
      id: mockResidentId,
      user_code: `USR${String(mockResidentId).padStart(6, '0')}`,
      frames_kept: 18,
      full_name: name,
      age: Number(age),
      apartment_number: apartment_number.trim(),
      status: 'active',
      frames: 18,
      isMock: true,
    },
  }
}
