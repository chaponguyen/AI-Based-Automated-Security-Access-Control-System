// Các cờ mock chỉ bật khi Vite nhận giá trị "1" trong file môi trường.
export const mockRegisterEnabled = import.meta.env.VITE_MOCK_REGISTER === '1'
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
let mockStaffId = 3
let mockStaff = [
  { id: 1, username: 'manager', full_name: 'Quản lý demo', role: 'manager', is_active: true, password: 'manager123', last_login_at: null, created_at: '2026-10-26T08:00:00Z' },
  { id: 2, username: 'security', full_name: 'Nhân viên an ninh demo', role: 'security', is_active: true, password: 'security123', last_login_at: null, created_at: '2026-10-26T08:05:00Z' },
]

// TODO(B17): bỏ phiên giả sau khi API đăng nhập B15 sẵn sàng.
export async function mockLogin(username, password) {
  if (!mockAuthEnabled) throw new Error('Mock xác thực đang tắt')
  if (username === 'locked') {
    const error = new Error('Tài khoản đang tạm khóa')
    error.response = { status: 423, data: { reason: 'locked', retry_after_s: 30 } }
    throw error
  }
  const account = mockStaff.find((item) => item.username === String(username || '').trim())
  if (!account || !account.is_active || account.password !== password) {
    const error = new Error('Sai tên đăng nhập hoặc mật khẩu')
    error.response = { status: 401, data: { reason: 'invalid_credentials' } }
    throw error
  }
  account.last_login_at = new Date().toISOString()
  mockSessionUser = { id: account.id, username: account.username, full_name: account.full_name, role: account.role }
  return { ...mockSessionUser }
}

export async function mockGetAuthMe() {
  return mockSessionUser ? { ...mockSessionUser } : null
}

export async function mockLogout() {
  mockSessionUser = null
  return { ok: true }
}

function staffPublicFields(staff) {
  const { password, ...publicFields } = staff
  return { ...publicFields }
}

function mockStaffError(status, reason) {
  const error = new Error(reason)
  error.response = { status, data: { reason } }
  return error
}

// TODO(B17): thay mock nhân viên bằng GET/POST/PATCH/DELETE /api/staff khi backend B15 sẵn sàng.
export async function mockGetStaff() {
  return mockStaff.map(staffPublicFields)
}

export async function mockCreateStaff(payload) {
  if (mockStaff.some((staff) => staff.username.toLocaleLowerCase('vi') === String(payload.username).trim().toLocaleLowerCase('vi'))) {
    throw mockStaffError(409, 'username_taken')
  }
  const created = {
    id: mockStaffId++,
    username: String(payload.username).trim(),
    full_name: String(payload.full_name).trim(),
    password: payload.password,
    role: payload.role,
    is_active: true,
    last_login_at: null,
    created_at: new Date().toISOString(),
  }
  mockStaff.push(created)
  return staffPublicFields(created)
}

export async function mockUpdateStaff(id, payload = {}, currentUserId) {
  const staff = mockStaff.find((item) => item.id === Number(id))
  if (!staff) throw mockStaffError(404, 'not_found')
  const demotes = payload.role && payload.role !== 'manager' && staff.role === 'manager'
  const disables = payload.is_active === false && staff.is_active
  if (Number(currentUserId) === staff.id && (demotes || disables)) throw mockStaffError(409, 'self_protected')
  const managerCount = mockStaff.filter((item) => item.role === 'manager' && item.is_active).length
  if (managerCount <= 1 && staff.role === 'manager' && (demotes || disables)) throw mockStaffError(409, 'last_manager')
  Object.assign(staff, payload)
  return staffPublicFields(staff)
}

export async function mockDeleteStaff(id, currentUserId) {
  const staff = mockStaff.find((item) => item.id === Number(id))
  if (!staff) throw mockStaffError(404, 'not_found')
  if (Number(currentUserId) === staff.id) throw mockStaffError(409, 'self_protected')
  if (staff.role === 'manager' && staff.is_active && mockStaff.filter((item) => item.role === 'manager' && item.is_active).length <= 1) {
    throw mockStaffError(409, 'last_manager')
  }
  mockStaff = mockStaff.filter((item) => item.id !== staff.id)
  return { ok: true }
}

function dispatchMockDoorState(data) {
  window.dispatchEvent(new CustomEvent('dashboard:mock-event', { detail: { event: 'door_state', data } }))
}

// TODO(B17): chỉ dùng khi VITE_MOCK_ADMIN=1; còn lại Dashboard gọi GET /api/door/status.
export async function mockGetDoorStatus() {
  const now = performance.now()
  const isOpen = mockDoorUntil > now
  const remainingSeconds = isOpen ? Math.ceil((mockDoorUntil - now) / 1000) : 0
  return {
    state: isOpen ? 'open' : 'closed',
    remaining_seconds: remainingSeconds,
    open_seconds: remainingSeconds,
    until: isOpen ? new Date(Date.now() + remainingSeconds * 1000).toISOString() : null,
    by: isOpen ? 'Nhân viên mô phỏng' : null,
  }
}

// TODO(B17): chỉ dùng khi VITE_MOCK_ADMIN=1; còn lại Dashboard gọi POST /api/door/open.
export async function mockOpenDoor(reason = '') {
  if (mockDoorUntil > performance.now()) {
    return { ...(await mockGetDoorStatus()), open_seconds: Math.ceil((mockDoorUntil - performance.now()) / 1000), already_open: true }
  }

  if (mockDoorTimer !== null) window.clearTimeout(mockDoorTimer)
  mockDoorUntil = performance.now() + 10000
  const openState = {
    state: 'open',
    remaining_seconds: 10,
    until: new Date(Date.now() + 10000).toISOString(),
    open_seconds: 10,
    by: 'Nhân viên mô phỏng',
    reason: reason || null,
    already_open: false,
  }
  dispatchMockDoorState(openState)
  mockDoorTimer = window.setTimeout(() => {
    mockDoorUntil = 0
    mockDoorTimer = null
    dispatchMockDoorState({ state: 'closed', until: null, remaining_seconds: 0, open_seconds: 0, by: null, reason: null })
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
