// Agent 3 — Thêm cư dân kèm đăng ký khuôn mặt, danh sách và bật/tắt quyền ra vào.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import LiveStream from '../components/LiveStream.jsx'
import RecordProgress from '../components/RecordProgress.jsx'
import Button from '../components/ui/Button.jsx'
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import { useDashboardSocket } from '../hooks/useDashboardSocket.js'
import { api, getApiErrorMessage } from '../services/api.js'
import { mockAdminEnabled, mockDeleteResident, mockIsResidentDeleted, mockRegisterEnabled, mockRegisterResident, mockRegistrationPrecheck, PREPARE_SECONDS } from '../services/mock.js'

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
  const { user } = useOutletContext() || {}
  const isManager = user?.role === 'manager'
  const { connected, cameraStatus, recording } = useDashboardSocket()
  const [form, setForm] = useState(emptyForm)
  const [errors, setErrors] = useState({})
  const [submitted, setSubmitted] = useState(false)
  const [notice, setNotice] = useState('')
  const [noticeError, setNoticeError] = useState(false)
  const [registrationPhase, setRegistrationPhase] = useState('idle')
  const [previewEnabled, setPreviewEnabled] = useState(false)
  const [precheckResult, setPrecheckResult] = useState(null)
  const [precheckError, setPrecheckError] = useState(false)
  const [duplicateResident, setDuplicateResident] = useState(null)
  const [countdown, setCountdown] = useState(PREPARE_SECONDS)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [residents, setResidents] = useState([])
  const [mockResidents, setMockResidents] = useState([])
  const [residentsLoading, setResidentsLoading] = useState(true)
  const [residentsError, setResidentsError] = useState('')
  const [search, setSearch] = useState('')
  const [pendingIds, setPendingIds] = useState(() => new Set())
  const [listNotice, setListNotice] = useState('')
  const [listNoticeError, setListNoticeError] = useState(false)
  const [residentToDelete, setResidentToDelete] = useState(null)
  const [deleteSubmitting, setDeleteSubmitting] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const registrationPhaseRef = useRef('idle')
  const registrationRequestStartedRef = useRef(false)
  const prepareTimerRef = useRef(null)
  const precheckPromiseRef = useRef(null)
  const precheckAbortRef = useRef(null)
  const previewEnabledRef = useRef(false)
  const previousPrecheckExistsRef = useRef(false)
  const consecutiveExistsRef = useRef(0)
  const duplicateModalShownRef = useRef(false)
  const duplicateModalOpenRef = useRef(false)
  const duplicateDialogButtonRef = useRef(null)
  const duplicateDialogReturnFocusRef = useRef(null)
  const countdownRef = useRef(PREPARE_SECONDS)
  const recordingAtStartRef = useRef(null)
  const formRef = useRef(form)
  formRef.current = form

  const abortPrecheck = () => {
    precheckAbortRef.current?.abort()
  }

  const openDuplicateDialog = (user) => {
    if (duplicateModalOpenRef.current) return
    duplicateDialogReturnFocusRef.current = document.activeElement
    duplicateModalOpenRef.current = true
    duplicateModalShownRef.current = true
    setDuplicateResident(user || {})
    if (registrationPhaseRef.current === 'checking') {
      registrationPhaseRef.current = 'idle'
      setRegistrationPhase('idle')
    }
  }

  async function confirmExistsAfterCurrentRequest() {
    const inFlight = precheckPromiseRef.current
    if (inFlight) await inFlight
    if (!duplicateModalOpenRef.current) await runPrecheck()
  }

  const acceptPrecheck = (data, { confirmExists = true } = {}) => {
    setPrecheckResult(data)
    setPrecheckError(false)
    if (data.state === 'exists') {
      consecutiveExistsRef.current = previousPrecheckExistsRef.current
        ? consecutiveExistsRef.current + 1
        : 1
      previousPrecheckExistsRef.current = true
      if (registrationPhaseRef.current === 'preparing') {
        if (prepareTimerRef.current !== null) window.clearInterval(prepareTimerRef.current)
        prepareTimerRef.current = null
        registrationPhaseRef.current = 'checking'
        setRegistrationPhase('checking')
        setCountdown(PREPARE_SECONDS)
        countdownRef.current = PREPARE_SECONDS
        setNotice('Đã tìm thấy cư dân trùng. Đã hủy bước chuẩn bị và chưa gửi yêu cầu đăng ký.')
        setNoticeError(true)
      }
      if (consecutiveExistsRef.current >= 2 && !duplicateModalShownRef.current) {
        if (duplicateModalOpenRef.current) duplicateModalShownRef.current = true
        else openDuplicateDialog(data.user)
      } else if (confirmExists && consecutiveExistsRef.current === 1) {
        void confirmExistsAfterCurrentRequest()
      }
      return
    }

    previousPrecheckExistsRef.current = false
    consecutiveExistsRef.current = 0
    duplicateModalShownRef.current = false
  }

  async function runPrecheck() {
    if (precheckPromiseRef.current) return precheckPromiseRef.current

    const controller = new AbortController()
    precheckAbortRef.current = controller
    let request
    request = (async () => {
      try {
        const data = mockRegisterEnabled
          ? await mockRegistrationPrecheck(formRef.current.full_name)
          : (await api.get('/registration/precheck', { signal: controller.signal })).data
        if (controller.signal.aborted) return null
        if (!['no_face', 'multiple_faces', 'low_quality', 'new', 'exists'].includes(data?.state)) {
          throw new Error('Phản hồi precheck không hợp lệ.')
        }
        acceptPrecheck(data)
        return data
      } catch (error) {
        if (controller.signal.aborted || error.code === 'ERR_CANCELED') return null
        setPrecheckError(true)
        return null
      } finally {
        if (precheckAbortRef.current === controller) precheckAbortRef.current = null
        if (precheckPromiseRef.current === request) precheckPromiseRef.current = null
      }
    })()
    precheckPromiseRef.current = request
    return request
  }

  const handlePreviewStatusChange = useCallback(({ enabled }) => {
    setPreviewEnabled(enabled)
    if (previewEnabledRef.current && !enabled) abortPrecheck()
    previewEnabledRef.current = enabled
  }, [])

  const closeDuplicateDialog = () => {
    duplicateModalOpenRef.current = false
    setDuplicateResident(null)
    window.requestAnimationFrame(() => duplicateDialogReturnFocusRef.current?.focus?.())
  }

  useEffect(() => {
    if (!duplicateResident) return undefined
    duplicateDialogButtonRef.current?.focus()
    const onKeyDown = (event) => {
      if (event.key === 'Escape') closeDuplicateDialog()
      if (event.key === 'Tab') {
        event.preventDefault()
        duplicateDialogButtonRef.current?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [duplicateResident])

  useEffect(() => () => abortPrecheck(), [])

  useEffect(() => {
    const canPoll = previewEnabled || registrationPhase === 'preparing'
    if (!canPoll || ['validating', 'recording'].includes(registrationPhase)) return undefined

    void runPrecheck()
    const timer = window.setInterval(() => {
      if (['validating', 'recording'].includes(registrationPhaseRef.current)) return
      void runPrecheck()
    }, 1000)
    return () => window.clearInterval(timer)
  }, [previewEnabled, registrationPhase])

  useEffect(() => {
    if (registrationPhase !== 'recording') {
      setElapsedMs(0)
      return undefined
    }
    const startedAt = Date.now()
    const timer = window.setInterval(() => setElapsedMs(Date.now() - startedAt), 100)
    return () => window.clearInterval(timer)
  }, [registrationPhase])

  useEffect(() => {
    if (registrationPhase !== 'preparing') return undefined
    const timer = window.setInterval(() => {
      if (registrationPhaseRef.current !== 'preparing') {
        window.clearInterval(timer)
        if (prepareTimerRef.current === timer) prepareTimerRef.current = null
        return
      }
      const remaining = Math.max(0, countdownRef.current - 1)
      countdownRef.current = remaining
      setCountdown(remaining)
      if (remaining === 0) {
        window.clearInterval(timer)
        if (prepareTimerRef.current === timer) prepareTimerRef.current = null
        registrationPhaseRef.current = 'validating'
        setRegistrationPhase('validating')
        void (async () => {
          let result = await runPrecheck()
          if (registrationPhaseRef.current !== 'validating') return
          if (!result) {
            registrationPhaseRef.current = 'idle'
            setRegistrationPhase('idle')
            setNotice('Không kiểm tra được khuôn mặt trước khi đăng ký. Vui lòng thử lại.')
            setNoticeError(true)
            return
          }
          if (result.state === 'exists') {
            result = await runPrecheck()
            if (registrationPhaseRef.current !== 'validating') return
            if (!result || result.state === 'exists') {
              registrationPhaseRef.current = 'idle'
              setRegistrationPhase('idle')
              setNotice('Đã tìm thấy cư dân trùng. Chưa gửi yêu cầu đăng ký.')
              setNoticeError(true)
              return
            }
          }
          registrationPhaseRef.current = 'recording'
          setRegistrationPhase('recording')
        })()
      }
    }, 1000)
    prepareTimerRef.current = timer
    return () => {
      window.clearInterval(timer)
      if (prepareTimerRef.current === timer) prepareTimerRef.current = null
    }
  }, [registrationPhase])

  const refreshResidents = useCallback(async () => {
    setResidentsLoading(true)
    setResidentsError('')
    try {
      const { data } = await api.get('/residents')
      setResidents(Array.isArray(data) ? data.filter((resident) => !mockAdminEnabled || !mockIsResidentDeleted(resident.id)) : [])
    } catch (error) {
      setResidentsError(getApiErrorMessage(error, 'Không tải được danh sách cư dân.'))
    } finally {
      setResidentsLoading(false)
    }
  }, [])

  useEffect(() => { void refreshResidents() }, [refreshResidents])

  const handleChange = (event) => {
    const { name, value } = event.target
    const nextForm = { ...form, [name]: value }
    setForm(nextForm)
    if (submitted || errors[name]) setErrors(validateResidentForm(nextForm))
    setNotice('')
    setNoticeError(false)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (registrationPhaseRef.current !== 'idle' || precheckResult?.state === 'exists') return
    setSubmitted(true)
    const nextErrors = validateResidentForm(form)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length === 0) {
      registrationPhaseRef.current = 'checking'
      setRegistrationPhase('checking')
      let result = await runPrecheck()
      if (registrationPhaseRef.current !== 'checking') return
      if (!result) {
        registrationPhaseRef.current = 'idle'
        setRegistrationPhase('idle')
        setNotice('Không kiểm tra được khuôn mặt. Vui lòng thử lại trước khi đăng ký.')
        setNoticeError(true)
        return
      }
      if (result.state === 'exists') {
        result = await runPrecheck()
        if (registrationPhaseRef.current !== 'checking') return
        if (!result || result.state === 'exists') {
          registrationPhaseRef.current = 'idle'
          setRegistrationPhase('idle')
          setNotice('Đã tìm thấy cư dân trùng. Không bắt đầu đếm ngược và chưa gửi yêu cầu đăng ký.')
          setNoticeError(true)
          return
        }
      }
      registrationPhaseRef.current = 'preparing'
      registrationRequestStartedRef.current = false
      countdownRef.current = PREPARE_SECONDS
      setCountdown(PREPARE_SECONDS)
      setNotice('')
      setNoticeError(false)
      setRegistrationPhase('preparing')
    } else {
      setNotice('Vui lòng sửa các mục được đánh dấu.')
      setNoticeError(true)
    }
  }

  const cancelPreparation = () => {
    if (registrationPhaseRef.current !== 'preparing') return
    if (prepareTimerRef.current !== null) {
      window.clearInterval(prepareTimerRef.current)
      prepareTimerRef.current = null
    }
    registrationPhaseRef.current = 'idle'
    registrationRequestStartedRef.current = false
    countdownRef.current = PREPARE_SECONDS
    setRegistrationPhase('idle')
    setCountdown(PREPARE_SECONDS)
    setNotice('Đã hủy bước chuẩn bị. Chưa gửi yêu cầu đăng ký.')
    setNoticeError(false)
  }

  const submitResident = async () => {
    setElapsedMs(0)
    setNotice('')
    setNoticeError(false)
    recordingAtStartRef.current = recording

    try {
      let result
      if (mockRegisterEnabled) {
        // TODO: chuyển sang POST thật khi B5 hoàn tất và bỏ cờ VITE_MOCK_REGISTER.
        result = await mockRegisterResident(form)
        setMockResidents((items) => [result.data, ...items])
      } else {
        const body = new FormData()
        body.append('full_name', form.full_name.trim())
        body.append('age', String(Number(form.age)))
        body.append('apartment_number', form.apartment_number.trim())
        result = await api.post('/residents', body, { timeout: 60000 })
        void refreshResidents()
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
      } else if (status === 409 && detail.reason === 'already_registered') {
        acceptPrecheck({ state: 'exists', exists: true, user: detail.user, similarity: detail.similarity, box: null }, { confirmExists: false })
        consecutiveExistsRef.current = 2
        previousPrecheckExistsRef.current = true
        openDuplicateDialog(detail.user)
        setNotice('Cư dân này đã tồn tại. Không lưu đăng ký trùng.')
      } else if (status === 409) {
        setNotice('Đang có lượt đăng ký khác. Vui lòng đợi rồi thử lại.')
      } else {
        setNotice(getApiErrorMessage(error, 'Đăng ký chưa thành công. Vui lòng thử lại.'))
      }
      setNoticeError(true)
    } finally {
      registrationPhaseRef.current = 'idle'
      registrationRequestStartedRef.current = false
      setRegistrationPhase('idle')
    }
  }

  useEffect(() => {
    if (registrationPhase !== 'recording' || registrationRequestStartedRef.current) return
    registrationRequestStartedRef.current = true
    recordingAtStartRef.current = recording
    void submitResident()
  }, [registrationPhase])

  const currentRecording = recording !== recordingAtStartRef.current ? recording : null
  const registrationBusy = registrationPhase !== 'idle'
  const registrationBlockedByDuplicate = precheckResult?.state === 'exists'
  const precheckStatusText = precheckError
    ? 'Không kiểm tra được khuôn mặt'
    : precheckResult?.state === 'multiple_faces'
      ? 'Có nhiều khuôn mặt'
      : precheckResult?.state === 'low_quality'
        ? 'Ảnh chưa đủ rõ'
        : precheckResult?.state === 'exists'
          ? `Đã tồn tại: ${precheckResult.user?.full_name || 'cư dân'}`
          : precheckResult?.state === 'new'
            ? 'Người mới, có thể đăng ký'
            : 'Đang tìm khuôn mặt...'
  const filteredResidents = [...mockResidents, ...residents].filter((resident) => {
    const query = search.trim().toLocaleLowerCase('vi')
    if (!query) return true
    return `${resident.full_name || ''} ${resident.apartment_number || ''}`.toLocaleLowerCase('vi').includes(query)
  })

  const toggleResidentStatus = async (resident) => {
    if (pendingIds.has(resident.id)) return
    const previousStatus = resident.status
    const nextStatus = previousStatus === 'active' ? 'inactive' : 'active'
    const updateResident = (items, id, status) => items.map((item) => item.id === id ? { ...item, status } : item)

    if (resident.isMock) {
      // TODO: mock cư dân không có trong backend; PATCH thật áp dụng cho cư dân đã lưu.
      setMockResidents((items) => updateResident(items, resident.id, nextStatus))
      setListNotice(nextStatus === 'active' ? 'Đã bật quyền ra vào cho cư dân mô phỏng.' : 'Đã tắt quyền ra vào cho cư dân mô phỏng.')
      setListNoticeError(false)
      return
    }

    setPendingIds((current) => new Set(current).add(resident.id))
    setResidents((items) => updateResident(items, resident.id, nextStatus))
    setListNotice('')
    try {
      await api.patch(`/residents/${resident.id}/status`, { status: nextStatus })
      setListNotice(nextStatus === 'active' ? 'Đã bật quyền ra vào.' : 'Đã tắt quyền ra vào.')
      setListNoticeError(false)
    } catch (error) {
      setResidents((items) => updateResident(items, resident.id, previousStatus))
      setListNotice(getApiErrorMessage(error, 'Không cập nhật được quyền cư dân. Trạng thái đã được hoàn lại.'))
      setListNoticeError(true)
    } finally {
      setPendingIds((current) => {
        const next = new Set(current)
        next.delete(resident.id)
        return next
      })
    }
  }

  const deleteResident = async () => {
    if (!residentToDelete || !isManager || deleteSubmitting) return
    setDeleteSubmitting(true)
    setDeleteError('')
    try {
      if (residentToDelete.isMock) {
        await mockDeleteResident(residentToDelete.id, residentToDelete)
      } else if (mockAdminEnabled) {
        await mockDeleteResident(residentToDelete.id, residentToDelete)
      } else {
        await api.delete(`/residents/${residentToDelete.id}`)
      }
      setMockResidents((items) => items.filter((item) => item.id !== residentToDelete.id))
      setResidents((items) => items.filter((item) => item.id !== residentToDelete.id))
      setPendingIds((current) => {
        const next = new Set(current)
        next.delete(residentToDelete.id)
        return next
      })
      setListNotice(`Đã xóa cư dân ${residentToDelete.full_name} (${residentToDelete.user_code || `USR${String(residentToDelete.id).padStart(6, '0')}`}).`)
      setListNoticeError(false)
      setResidentToDelete(null)
    } catch (error) {
      setDeleteError(getApiErrorMessage(error, 'Không xóa được cư dân. Vui lòng thử lại.'))
    } finally {
      setDeleteSubmitting(false)
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

      {isManager && <div className="resident-registration-layout">
        <section className="panel resident-preview-panel">
          <div className="section-heading">
            <div><p className="eyebrow">CĂN CHỈNH KHUÔN MẶT</p><h2>Xem trước camera</h2></div>
          </div>
          <LiveStream
            cameraStatus={cameraStatus}
            connected={connected}
            onStatusChange={handlePreviewStatusChange}
            startOnMount={registrationBusy}
            disabled={registrationBusy}
            startLabel="Bật xem trước để căn mặt"
            stopLabel="Tắt xem trước"
          />
          {(previewEnabled || ['checking', 'preparing', 'validating'].includes(registrationPhase)) && (
            <p className={`registration-precheck-chip${registrationBlockedByDuplicate ? ' registration-precheck-chip--exists' : ''}${precheckError ? ' registration-precheck-chip--error' : ''}`} role="status" aria-live="polite">
              {precheckStatusText}
            </p>
          )}
          <p className="resident-preview-caption">Ngồi cách camera khoảng nửa mét, nhìn thẳng, đủ sáng, chỉ một người trong khung.</p>
        </section>

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
                disabled={registrationBusy}
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
                disabled={registrationBusy}
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
                disabled={registrationBusy}
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

          <p className="muted form-hint">Bạn có {PREPARE_SECONDS} giây căn chỉnh. Backend chỉ bắt đầu quay sau khi hết đếm ngược.</p>
          {registrationPhase === 'preparing' && (
            <div className="prepare-countdown" role="status" aria-live="assertive">
              <strong>{countdown}</strong>
              <div>
                <p>Chuẩn bị, nhìn thẳng vào camera. Sắp quay</p>
                <button type="button" onClick={cancelPreparation}>Hủy</button>
              </div>
            </div>
          )}
          {registrationPhase === 'recording' && (
            <div className="registration-progress">
              <RecordProgress elapsedMs={elapsedMs} recording={currentRecording} />
            </div>
          )}
          <div className="resident-form__actions">
            <button className="button button--primary" type="submit" disabled={registrationBusy || registrationBlockedByDuplicate} aria-describedby={registrationBlockedByDuplicate ? 'duplicate-registration-reason' : undefined}>
              {registrationPhase === 'checking' || registrationPhase === 'validating' ? 'Đang kiểm tra khuôn mặt…' : registrationPhase === 'preparing' ? 'Đang chuẩn bị…' : registrationPhase === 'recording' ? 'Đang quay 3 giây…' : 'Quay 3 giây và lưu cư dân'}
            </button>
            {registrationBlockedByDuplicate && <p id="duplicate-registration-reason" className="form-notice form-notice--error">Không thể đăng ký vì khuôn mặt đã tồn tại.</p>}
            {notice && <p className={noticeError ? 'form-notice form-notice--error' : 'form-notice'} role="status">{notice}</p>}
          </div>
        </form>
        </section>
      </div>}

      <section className="panel resident-list-panel">
        <div className="section-heading resident-list-heading">
          <div><p className="eyebrow">DANH SÁCH</p><h2>Cư dân đã đăng ký</h2></div>
          <Button variant="secondary" size="sm" onClick={() => void refreshResidents()} disabled={residentsLoading}>Làm mới</Button>
        </div>
        <label className="resident-search" htmlFor="resident-search">
          <span>Tìm theo tên hoặc căn hộ</span>
          <input id="resident-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Nhập tên hoặc mã căn hộ" />
        </label>
        {residentsLoading && <p className="loading-state" role="status">Đang tải danh sách cư dân…</p>}
        {!residentsLoading && residentsError && (
          <div className="error-state" role="alert"><p>{residentsError}</p><button type="button" onClick={() => void refreshResidents()}>Thử lại</button></div>
        )}
        {!residentsLoading && !residentsError && filteredResidents.length === 0 && (
          <p className="empty-state">{search ? 'Không tìm thấy cư dân phù hợp.' : 'Chưa có cư dân nào. Hãy đăng ký cư dân đầu tiên ở biểu mẫu phía trên.'}</p>
        )}
        {filteredResidents.length > 0 && (
          <div className="table-wrap">
            <table className={`resident-table${isManager ? ' resident-table--manager' : ''}`}>
              <thead><tr><th>Mã cư dân</th><th>Họ và tên</th><th>Tuổi</th><th>Căn hộ</th><th>Số khung</th><th>Trạng thái</th>{isManager && <><th>Quyền ra vào</th><th>Thao tác</th></>}</tr></thead>
              <tbody>{filteredResidents.map((resident) => (
                <tr key={`${resident.isMock ? 'mock' : 'resident'}-${resident.id}`}>
                  <td>{resident.user_code || `USR${String(resident.id).padStart(6, '0')}`}{resident.isMock && <small className="mock-label"> Mô phỏng</small>}</td>
                  <td>{resident.full_name}</td>
                  <td>{resident.age}</td>
                  <td>{resident.apartment_number}</td>
                  <td>{resident.frames ?? resident.frames_kept ?? 0}</td>
                  <td><span className={`status-chip ${resident.status === 'active' ? 'status-chip--good' : 'status-chip--warning'}`}>{resident.status === 'active' ? 'Đang hoạt động' : 'Đã tắt'}</span></td>
                  {isManager && <>
                    <td><Button variant="secondary" size="sm" disabled={pendingIds.has(resident.id)} onClick={() => void toggleResidentStatus(resident)}>{pendingIds.has(resident.id) ? 'Đang lưu…' : resident.status === 'active' ? 'Tắt quyền' : 'Bật quyền'}</Button></td>
                    <td><Button variant="danger" size="sm" onClick={() => { setDeleteError(''); setResidentToDelete(resident) }}>Xóa</Button></td>
                  </>}
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {listNotice && <p className={listNoticeError ? 'form-notice form-notice--error' : 'form-notice'} role="status">{listNotice}</p>}
      </section>

      <ConfirmDialog
        open={Boolean(residentToDelete)}
        onClose={() => { if (!deleteSubmitting) setResidentToDelete(null) }}
        onConfirm={() => void deleteResident()}
        title="Xóa cư dân?"
        description={residentToDelete ? `${residentToDelete.full_name} · ${residentToDelete.user_code || `USR${String(residentToDelete.id).padStart(6, '0')}`}` : ''}
        confirmLabel="Xóa cư dân"
        cancelLabel="Hủy"
        loading={deleteSubmitting}
        danger
      >
        <p className="resident-delete-warning">Thao tác này xóa cả khuôn mặt đã lưu và không thể hoàn tác.</p>
        {deleteError && <ErrorState message={deleteError} />}
      </ConfirmDialog>

      {duplicateResident && (
        <div className="resident-modal-backdrop">
          <section className="resident-duplicate-modal" role="dialog" aria-modal="true" aria-labelledby="resident-duplicate-title" aria-describedby="resident-duplicate-details">
            <h2 id="resident-duplicate-title">Cư dân này đã tồn tại</h2>
            <div id="resident-duplicate-details" className="resident-duplicate-details">
              <p><strong>{duplicateResident.full_name || 'Không rõ tên'}</strong>{duplicateResident.status === 'inactive' && ' (đang bị tắt quyền)'}</p>
              <p>Mã cư dân: {duplicateResident.user_code || '—'}</p>
              <p>Căn hộ: {duplicateResident.apartment_number || '—'}</p>
            </div>
            <button ref={duplicateDialogButtonRef} type="button" className="button button--primary" onClick={closeDuplicateDialog}>Đã hiểu</button>
          </section>
        </div>
      )}
    </main>
  )
}
