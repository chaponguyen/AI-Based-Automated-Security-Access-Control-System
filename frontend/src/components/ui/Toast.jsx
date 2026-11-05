import { CloseIcon } from './icons.jsx'

const tones = new Set(['info', 'success', 'warning', 'danger'])

export default function Toast({ open = true, tone = 'info', title, message, onClose, className = '' }) {
  if (!open) return null
  const safeTone = tones.has(tone) ? tone : 'info'
  const classes = ['ui-toast', `ui-toast--${safeTone}`, className].filter(Boolean).join(' ')
  return (
    <div className={classes} role={tone === 'danger' ? 'alert' : 'status'} aria-live={tone === 'danger' ? 'assertive' : 'polite'}>
      <div>{title && <strong>{title}</strong>}{message && <p>{message}</p>}</div>
      {onClose && <button className="ui-button ui-button--ghost ui-toast__close" type="button" onClick={onClose} aria-label="Đóng thông báo"><CloseIcon /></button>}
    </div>
  )
}
