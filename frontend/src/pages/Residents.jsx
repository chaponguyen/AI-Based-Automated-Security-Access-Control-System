// Agent 3 — Thêm cư dân kèm đăng ký khuôn mặt, danh sách và bật/tắt quyền ra vào.
import { useEffect, useRef, useState } from 'react'
import LiveStream from '../components/LiveStream.jsx'
import RecordProgress from '../components/RecordProgress.jsx'
import { useDashboardSocket } from '../hooks/useDashboardSocket.js'
import { api, getApiErrorMessage } from '../services/api.js'
import { mockRegisterEnabled, mockRegisterResident } from '../services/mock.js'

const emptyForm = { full_name: '', age: '', apartment_number: '' }

function validateResidentForm(form) {
  const errors = {}
  const fullName = form.full_name.trim()
  const age = form.age.trim()
  const apartment = form.apartment_number.trim()

  if (!fullName) errors.full_name = 'Vui lòng nhập họ và tên.'
  else if (fullName.length > 150) errors.full_name = 'Họ và tên không được vượt quá 150 ký tự.'

  if (!age) errors.age = 'Vui lòng nhập tuổi.'
  else if (!/^\d+$/.test(age) || !Number.isInteger(Number(age)) || Number(age) < 1 || Number(age) > 120) {
    errors.age = 'Tuổi phải là số nguyên từ 1 đến 120.'
  }

  if (!apartment) errors.apartment_number = 'Vui lòng nhập căn hộ.'
  else if (apartment.length > 20) errors.apartment_number = 'Căn hộ không được vượt quá 20 ký tự.'

  return errors
}

export default function Residents() {
  const { connected, cameraStatus, recording } = useDashboardSocket()
  const [form, setForm] = useState(emptyForm)
  const [errors, setErrors] = useState({})
  const [submitted, setSubmitted] = useState(false)
  const [notice, setNotice] = useState('')
  const [noticeError, setNoticeError] = useState(false)
  const [registering, setRegistering] = useState(false)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [residents, setResidents] = useState([])
  const recordingAtStartRef = useRef(null)

  useEffect(() => {
    if (!registering) {
      setElapsedMs(0)
      return undefined
    }
    const startedAt = Date.now()
    const timer = window.setInterval(() => setElapsedMs(Date.now() - startedAt), 100)
    return () => window.clearInterval(timer)
  }, [registering])

  const refreshResidents = async () => {
    if (mockRegisterEnabled) return
    try {
      const { data } = await api.get('/residents')
      setResidents(Array.isArray(data) ? data : [])
    } catch {
      // CP-06 hiển thị lỗi danh sách và cho phép tải lại.
    }
  }

  const handleChange = (event) => {
    const { name, value } = event.target
    const nextForm = { ...form, [name]: value }
    setForm(nextForm)
    if (submitted || errors[name]) setErrors(validateResidentForm(nextForm))
    setNotice('')
    setNoticeError(false)
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    if (registering) return
    setSubmitted(true)
    const nextErrors = validateResidentForm(form)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length === 0) {
      void registerResident()
    } else {
      setNotice('Vui lòng sửa các mục được đánh dấu.')
      setNoticeError(true)
    }
  }

  const registerResident = async () => {
    setRegistering(true)
    setElapsedMs(0)
    setNotice('')
    setNoticeError(false)
    recordingAtStartRef.current = recording

    try {
      let result
      if (mockRegisterEnabled) {
        // TODO: chuyển sang POST thật khi B5 hoàn tất và bỏ cờ VITE_MOCK_REGISTER.
        result = await mockRegisterResident(form)
        setResidents((items) => [result.data, ...items])
      } else {
        const body = new FormData()
        body.append('full_name', form.full_name.trim())
        body.append('age', String(Number(form.age)))
        body.append('apartment_number', form.apartment_number.trim())
        result = await api.post('/residents', body)
        await refreshResidents()
      }

      setNotice(`Đăng ký thành công: ${result.data.user_code} · giữ lại ${result.data.frames_kept} khung.`)
      setNoticeError(false)
      setForm(emptyForm)
      setErrors({})
      setSubmitted(false)
    } catch (error) {
      const status = error.response?.status
      const detail = error.response?.data || {}
      if (status === 422 && detail.reason === 'not_enough_quality_frames') {
        setNotice(`Chỉ thu được ${detail.good ?? 0}/${detail.required ?? 15} khung đạt, hãy nhìn thẳng và đủ sáng rồi thử lại.`)
      } else if (status === 409) {
        setNotice('Đang có lượt đăng ký khác. Vui lòng đợi rồi thử lại.')
      } else {
        setNotice(getApiErrorMessage(error, 'Đăng ký chưa thành công. Vui lòng thử lại.'))
      }
      setNoticeError(true)
    } finally {
      setRegistering(false)
    }
  }

  const currentRecording = recording !== recordingAtStartRef.current ? recording : null

  return (
    <main className="page residents-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">QUẢN LÝ CƯ DÂN</p>
          <h1>Cư dân</h1>
          <p className="muted">Mỗi cư dân được đăng ký cùng khuôn mặt trong một bước.</p>
        </div>
      </header>

      <section className="panel resident-form-panel">
        <div className="section-heading">
          <div><p className="eyebrow">ĐĂNG KÝ MỚI</p><h2>Thông tin cư dân</h2></div>
        </div>
        <form className="resident-form" onSubmit={handleSubmit} noValidate>
          <div className="resident-form__grid">
            <label className="field" htmlFor="resident-full-name">
              <span>Họ và tên <b aria-hidden="true">*</b></span>
              <input
                id="resident-full-name"
                name="full_name"
                value={form.full_name}
                disabled={registering}
                onChange={handleChange}
                onBlur={() => setErrors(validateResidentForm(form))}
                maxLength={150}
                autoComplete="name"
                aria-invalid={Boolean(errors.full_name)}
                aria-describedby={errors.full_name ? 'resident-full-name-error' : undefined}
              />
              {errors.full_name && <small className="field-error" id="resident-full-name-error">{errors.full_name}</small>}
            </label>

            <label className="field" htmlFor="resident-age">
              <span>Tuổi <b aria-hidden="true">*</b></span>
              <input
                id="resident-age"
                name="age"
                type="number"
                inputMode="numeric"
                min="1"
                max="120"
                step="1"
                value={form.age}
                disabled={registering}
                onChange={handleChange}
                onBlur={() => setErrors(validateResidentForm(form))}
                aria-invalid={Boolean(errors.age)}
                aria-describedby={errors.age ? 'resident-age-error' : undefined}
              />
              {errors.age && <small className="field-error" id="resident-age-error">{errors.age}</small>}
            </label>

            <label className="field" htmlFor="resident-apartment">
              <span>Căn hộ <b aria-hidden="true">*</b></span>
              <input
                id="resident-apartment"
                name="apartment_number"
                value={form.apartment_number}
                disabled={registering}
                onChange={handleChange}
                onBlur={() => setErrors(validateResidentForm(form))}
                maxLength={20}
                placeholder="Ví dụ: A-1203"
                aria-invalid={Boolean(errors.apartment_number)}
                aria-describedby={errors.apartment_number ? 'resident-apartment-error' : undefined}
              />
              {errors.apartment_number && <small className="field-error" id="resident-apartment-error">{errors.apartment_number}</small>}
            </label>
          </div>

          <p className="muted form-hint">Backend sẽ quay 3 giây từ camera riêng; trình duyệt không mở camera.</p>
          {registering && (
            <div className="registration-progress">
              <RecordProgress elapsedMs={elapsedMs} recording={currentRecording} />
              <LiveStream cameraStatus={cameraStatus} connected={connected} startOnMount />
            </div>
          )}
          <div className="resident-form__actions">
            <button className="button button--primary" type="submit" disabled={registering}>
              {registering ? 'Đang quay 3 giây…' : 'Quay 3 giây và lưu cư dân'}
            </button>
            {notice && <p className={noticeError ? 'form-notice form-notice--error' : 'form-notice'} role="status">{notice}</p>}
          </div>
        </form>
      </section>
    </main>
  )
}
