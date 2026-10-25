// Bảng dịch reason duy nhất dùng trong giao diện.
export const reasonLabels = {
  ok: 'Hợp lệ',
  not_matched: 'Không nhận ra khuôn mặt',
  spoof_detected: 'Nghi ngờ giả mạo bằng ảnh hoặc video',
  inactive_user: 'Cư dân đã bị tắt quyền',
  no_face: 'Không thấy khuôn mặt trong khung hình',
  multiple_faces: 'Có nhiều khuôn mặt trong khung',
  low_quality: 'Chất lượng khuôn mặt chưa đạt',
}

export function getReasonLabel(reason) {
  return reasonLabels[reason] || reason || 'Chưa có thông tin'
}
