// Các cờ mock chỉ bật khi Vite nhận giá trị "1" trong file môi trường.
export const mockRegisterEnabled = import.meta.env.VITE_MOCK_REGISTER === '1'
export const mockEventsEnabled = import.meta.env.VITE_MOCK_EVENTS === '1'
