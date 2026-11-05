import Button from './Button.jsx'

export default function ErrorState({ title = 'Không tải được dữ liệu', message, onRetry, retryLabel = 'Thử lại', className = '' }) {
  const classes = ['ui-error-state', className].filter(Boolean).join(' ')
  return (
    <div className={classes} role="alert">
      <span className="ui-error-state__mark" aria-hidden="true">!</span>
      <div>
        <h3>{title}</h3>
        {message && <p>{message}</p>}
      </div>
      {onRetry && <Button variant="secondary" size="sm" onClick={onRetry}>{retryLabel}</Button>}
    </div>
  )
}
