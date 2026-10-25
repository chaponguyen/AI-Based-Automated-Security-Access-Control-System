// Các cờ mock chỉ bật khi Vite nhận giá trị "1" trong file môi trường.
export const mockRegisterEnabled = import.meta.env.VITE_MOCK_REGISTER === '1'
export const mockEventsEnabled = import.meta.env.VITE_MOCK_EVENTS === '1'

let mockResidentId = 900000

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
