import { useCallback, useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import Badge from '../components/ui/Badge.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import FormField from '../components/ui/FormField.jsx'
import Input from '../components/ui/Input.jsx'
import Modal from '../components/ui/Modal.jsx'
import Select from '../components/ui/Select.jsx'
import Table from '../components/ui/Table.jsx'
import Toast from '../components/ui/Toast.jsx'
import { api, getApiErrorMessage } from '../services/api.js'
import {
  mockAdminEnabled,
  mockCreateStaff,
  mockDeleteStaff,
  mockGetStaff,
  mockUpdateStaff,
} from '../services/mock.js'
import { formatDate, formatDateTime } from '../utils/time.js'

const emptyForm = { username: '', full_name: '', password: '', role: 'security' }

function staffErrorMessage(error) {
  const reason = error?.response?.data?.reason
  if (reason === 'last_manager') return 'Không thể xóa hoặc hạ quyền quản lý cuối cùng.'
  if (reason === 'self_protected') return 'Bạn không thể tự xóa hoặc tự hạ quyền chính mình.'
  if (reason === 'username_taken') return 'Tên đăng nhập đã tồn tại.'
  return getApiErrorMessage(error, 'Không thực hiện được thao tác nhân viên. Vui lòng thử lại.')
}

function validateForm(form, editing) {
  const errors = {}
  if (!form.username.trim() && !editing) errors.username = 'Vui lòng nhập tên đăng nhập.'
  if (!form.full_name.trim()) errors.full_name = 'Vui lòng nhập họ tên.'
  if (!editing && form.password.length < 8) errors.password = 'Mật khẩu phải có ít nhất 8 ký tự.'
  if (editing && form.password && form.password.length < 8) errors.password = 'Mật khẩu mới phải có ít nhất 8 ký tự.'
  if (!['manager', 'security'].includes(form.role)) errors.role = 'Hãy chọn vai trò hợp lệ.'
  return errors
}

export default function Staff() {
  const { user } = useOutletContext() || {}
  const isManager = user?.role === 'manager'
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingStaff, setEditingStaff] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [formErrors, setFormErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [pendingId, setPendingId] = useState(null)
  const [staffToDelete, setStaffToDelete] = useState(null)
  const [deleteError, setDeleteError] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [toast, setToast] = useState('')

  const loadStaff = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = mockAdminEnabled ? await mockGetStaff() : (await api.get('/staff')).data
      setRows(Array.isArray(data) ? data : [])
    } catch (loadError) {
      setError(getApiErrorMessage(loadError, 'Không tải được danh sách nhân viên.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { if (isManager) void loadStaff() }, [isManager, loadStaff, retryKey])

  const openCreate = () => {
    setEditingStaff(null)
    setForm(emptyForm)
    setFormErrors({})
    setFormError('')
    setModalOpen(true)
  }

  const openEdit = (staff) => {
    setEditingStaff(staff)
    setForm({ username: staff.username, full_name: staff.full_name || '', password: '', role: staff.role })
    setFormErrors({})
    setFormError('')
    setModalOpen(true)
  }

  const closeForm = useCallback(() => {
    if (submitting) return
    setModalOpen(false)
  }, [submitting])

  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setFormErrors((current) => ({ ...current, [name]: '' }))
    setFormError('')
  }

  const submitForm = async (event) => {
    event.preventDefault()
    if (!isManager || submitting) return
    const validationErrors = validateForm(form, Boolean(editingStaff))
    setFormErrors(validationErrors)
    if (Object.keys(validationErrors).length) return

    setSubmitting(true)
    setFormError('')
    const payload = editingStaff
      ? { full_name: form.full_name.trim(), role: form.role, ...(form.password ? { password: form.password } : {}) }
      : { username: form.username.trim(), full_name: form.full_name.trim(), password: form.password, role: form.role }
    try {
      if (mockAdminEnabled) {
        if (editingStaff) await mockUpdateStaff(editingStaff.id, payload, user.id)
        else await mockCreateStaff(payload)
      } else if (editingStaff) {
        await api.patch(`/staff/${editingStaff.id}`, payload)
      } else {
        await api.post('/staff', payload)
      }
      setModalOpen(false)
      setToast({ tone: 'success', message: editingStaff ? 'Đã cập nhật tài khoản nhân viên.' : 'Đã tạo tài khoản nhân viên.' })
      await loadStaff()
    } catch (saveError) {
      setFormError(staffErrorMessage(saveError))
    } finally {
      setSubmitting(false)
    }
  }

  const toggleActive = async (staff) => {
    if (!isManager || pendingId !== null) return
    setPendingId(staff.id)
    try {
      if (mockAdminEnabled) await mockUpdateStaff(staff.id, { is_active: !staff.is_active }, user.id)
      else await api.patch(`/staff/${staff.id}`, { is_active: !staff.is_active })
      setToast({ tone: 'success', message: staff.is_active ? 'Đã tắt tài khoản nhân viên.' : 'Đã bật tài khoản nhân viên.' })
      await loadStaff()
    } catch (updateError) {
      setToast({ tone: 'danger', message: staffErrorMessage(updateError) })
    } finally {
      setPendingId(null)
    }
  }

  const confirmDelete = async () => {
    if (!staffToDelete || !isManager || deleting) return
    setDeleting(true)
    setDeleteError('')
    try {
      if (mockAdminEnabled) await mockDeleteStaff(staffToDelete.id, user.id)
      else await api.delete(`/staff/${staffToDelete.id}`)
      setStaffToDelete(null)
      setToast({ tone: 'success', message: `Đã xóa tài khoản ${staffToDelete.username}.` })
      await loadStaff()
    } catch (deleteRequestError) {
      setDeleteError(staffErrorMessage(deleteRequestError))
    } finally {
      setDeleting(false)
    }
  }

  const columns = useMemo(() => [
    { key: 'username', label: 'Tên đăng nhập' },
    { key: 'full_name', label: 'Họ tên' },
    { key: 'role', label: 'Vai trò', render: (staff) => <Badge tone={staff.role === 'manager' ? 'info' : 'neutral'}>{staff.role === 'manager' ? 'Quản lý' : 'Nhân viên an ninh'}</Badge> },
    { key: 'is_active', label: 'Trạng thái', render: (staff) => <Badge tone={staff.is_active ? 'success' : 'warning'}>{staff.is_active ? 'Đang hoạt động' : 'Đã tắt'}</Badge> },
    { key: 'last_login_at', label: 'Đăng nhập gần nhất', render: (staff) => formatDateTime(staff.last_login_at) },
    { key: 'created_at', label: 'Ngày tạo', render: (staff) => formatDate(staff.created_at) },
    { key: 'actions', label: 'Thao tác', render: (staff) => (
      <div className="staff-action-group">
        <Button variant="secondary" size="sm" onClick={() => openEdit(staff)} aria-label={`Sửa ${staff.username}`}>Sửa</Button>
        <Button variant="secondary" size="sm" onClick={() => void toggleActive(staff)} disabled={pendingId !== null} aria-label={`${staff.is_active ? 'Tắt' : 'Bật'} ${staff.username}`}>
          {pendingId === staff.id ? 'Đang lưu…' : staff.is_active ? 'Tắt' : 'Bật'}
        </Button>
        <Button variant="danger" size="sm" onClick={() => { setDeleteError(''); setStaffToDelete(staff) }} aria-label={`Xóa ${staff.username}`}>Xóa</Button>
      </div>
    ) },
  ], [pendingId])

  if (!isManager) return <main className="page"><ErrorState title="Không có quyền truy cập" message="Trang nhân viên chỉ dành cho quản lý." /></main>

  const editing = Boolean(editingStaff)
  return (
    <main className="page staff-page">
      <header className="page-header">
        <div><p className="eyebrow">QUẢN TRỊ</p><h1>Nhân viên</h1><p className="muted">Tạo và quản lý tài khoản có quyền vận hành hệ thống.</p></div>
        <Button onClick={openCreate}>Thêm nhân viên</Button>
      </header>
      {toast && <Toast tone={toast.tone} message={toast.message} onClose={() => setToast('')} />}
      <Card className="staff-panel">
        <Table
          columns={columns}
          rows={rows}
          rowKey="id"
          loading={loading}
          error={error}
          onRetry={() => setRetryKey((key) => key + 1)}
          emptyTitle="Chưa có tài khoản nhân viên"
          emptyDescription="Tạo tài khoản đầu tiên để cấp quyền truy cập hệ thống."
          className="staff-table-container"
        />
      </Card>

      <Modal
        open={modalOpen}
        onClose={closeForm}
        title={editing ? 'Cập nhật nhân viên' : 'Tạo tài khoản nhân viên'}
        description={editing ? `Tài khoản ${editingStaff?.username}` : 'Mật khẩu phải có ít nhất 8 ký tự.'}
        className="staff-modal"
        footer={(
          <>
            <Button variant="secondary" onClick={closeForm} disabled={submitting}>Hủy</Button>
            <Button type="submit" form="staff-form" loading={submitting}>{editing ? 'Lưu thay đổi' : 'Tạo tài khoản'}</Button>
          </>
        )}
      >
        <form id="staff-form" className="staff-form" onSubmit={submitForm}>
          {!editing && <FormField id="staff-username" label="Tên đăng nhập" error={formErrors.username} required>
            <Input id="staff-username" name="username" autoComplete="username" value={form.username} onChange={updateField} maxLength={80} required error={formErrors.username} />
          </FormField>}
          <FormField id="staff-full-name" label="Họ tên" error={formErrors.full_name} required>
            <Input id="staff-full-name" name="full_name" autoComplete="name" value={form.full_name} onChange={updateField} maxLength={150} required error={formErrors.full_name} />
          </FormField>
          <FormField id="staff-password" label={editing ? 'Đặt lại mật khẩu' : 'Mật khẩu'} description={editing ? 'Để trống nếu không đổi mật khẩu.' : 'Tối thiểu 8 ký tự.'} error={formErrors.password} required={!editing}>
            <Input id="staff-password" name="password" type="password" autoComplete={editing ? 'new-password' : 'new-password'} value={form.password} onChange={updateField} minLength={8} required={!editing} error={formErrors.password} />
          </FormField>
          <FormField id="staff-role" label="Vai trò" error={formErrors.role} required>
            <Select id="staff-role" name="role" value={form.role} onChange={updateField} error={formErrors.role}>
              <option value="security">Nhân viên an ninh</option>
              <option value="manager">Quản lý</option>
            </Select>
          </FormField>
          {formError && <ErrorState message={formError} />}
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(staffToDelete)}
        onClose={() => { if (!deleting) setStaffToDelete(null) }}
        onConfirm={() => void confirmDelete()}
        title="Xóa tài khoản nhân viên?"
        description={staffToDelete ? `${staffToDelete.full_name} · ${staffToDelete.username}` : ''}
        confirmLabel="Xóa tài khoản"
        cancelLabel="Hủy"
        loading={deleting}
        danger
      >
        <p className="staff-delete-warning">Nhân viên sẽ mất quyền đăng nhập vào hệ thống.</p>
        {deleteError && <ErrorState message={deleteError} />}
      </ConfirmDialog>
    </main>
  )
}
