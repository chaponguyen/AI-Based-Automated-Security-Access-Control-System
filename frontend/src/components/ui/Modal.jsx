import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { CloseIcon } from './icons.jsx'

const focusableSelector = 'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'

export default function Modal({ open, onClose, title, description, children, footer, tone = 'default', labelledBy, className = '' }) {
  const dialogRef = useRef(null)
  const closeRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const previousFocus = document.activeElement
    closeRef.current?.focus()
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose?.()
      }
      if (event.key !== 'Tab') return
      const items = [...(dialogRef.current?.querySelectorAll(focusableSelector) || [])]
      if (items.length === 0) {
        event.preventDefault()
        dialogRef.current?.focus()
        return
      }
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      previousFocus?.focus?.()
    }
  }, [open, onClose])

  if (!open || typeof document === 'undefined') return null
  const titleId = labelledBy || 'ui-modal-title'
  return createPortal(
    <div className="ui-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose?.() }}>
      <section
        {...(tone === 'danger' ? { 'data-tone': 'danger' } : {})}
        ref={dialogRef}
        className={['ui-modal', className].filter(Boolean).join(' ')}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? `${titleId}-description` : undefined}
        tabIndex={-1}
      >
        <header className="ui-modal__header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description && <p id={`${titleId}-description`}>{description}</p>}
          </div>
          <button ref={closeRef} className="ui-button ui-button--ghost ui-modal__close" type="button" onClick={onClose} aria-label="Đóng hộp thoại"><CloseIcon /></button>
        </header>
        {children && <div className="ui-modal__body">{children}</div>}
        {footer && <footer className="ui-modal__footer">{footer}</footer>}
      </section>
    </div>,
    document.body,
  )
}
