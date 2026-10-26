// Các cờ mock chỉ bật khi Vite nhận giá trị "1" trong file môi trường.
export const mockRegisterEnabled = import.meta.env.VITE_MOCK_REGISTER === '1'
export const mockEventsEnabled = import.meta.env.VITE_MOCK_EVENTS === '1'
// TODO(B17): bỏ mock quản trị sau khi backend B15/B16 sẵn sàng.
export const mockAdminEnabled = import.meta.env.VITE_MOCK_ADMIN === '1'
const configuredPrepareSeconds = Number(import.meta.env.VITE_REGISTER_PREPARE_SECONDS)
export const PREPARE_SECONDS = Number.isFinite(configuredPrepareSeconds) && configuredPrepareSeconds >= 1
  ? Math.floor(configuredPrepareSeconds)
  : 5

let mockResidentId = 900000
const mockDeletedResidentIds = new Set()
let mockDoorUntil = 0
let mockDoorTimer = null

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
