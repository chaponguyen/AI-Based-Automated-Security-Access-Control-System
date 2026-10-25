// Agent 3 — Form (họ tên, tuổi, căn hộ) + quay 3 giây (useCamera + RecordProgress) + gửi frames. Danh sách + bật/tắt active/inactive. Không có cư dân nào tồn tại mà thiếu khuôn mặt.
import { useState } from 'react'

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
  const [form, setForm] = useState(emptyForm)
  const [errors, setErrors] = useState({})
  const [submitted, setSubmitted] = useState(false)
  const [notice, setNotice] = useState('')

  const handleChange = (event) => {
    const { name, value } = event.target
    const nextForm = { ...form, [name]: value }
    setForm(nextForm)
    if (submitted || errors[name]) setErrors(validateResidentForm(nextForm))
    setNotice('')
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    setSubmitted(true)
    const nextErrors = validateResidentForm(form)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length === 0) {
      setNotice('Thông tin hợp lệ. Có thể bắt đầu quay để đăng ký khuôn mặt.')
    } else {
      setNotice('Vui lòng sửa các mục được đánh dấu.')
    }
  }

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

          <p className="muted form-hint">Thông tin được kiểm tra trên giao diện trước khi gửi lên backend.</p>
          <div className="resident-form__actions">
            <button className="button button--primary" type="submit">Kiểm tra thông tin</button>
            {notice && <p className={Object.keys(errors).length ? 'form-notice form-notice--error' : 'form-notice'} role="status">{notice}</p>}
          </div>
        </form>
      </section>
    </main>
  )
}
