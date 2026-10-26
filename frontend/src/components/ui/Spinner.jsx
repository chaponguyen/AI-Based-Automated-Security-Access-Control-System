export default function Spinner({ size = 'md', className = '', label = 'Đang tải' }) {
  const safeSize = ['sm', 'md', 'lg'].includes(size) ? size : 'md'
  const classes = ['ui-spinner', safeSize === 'md' ? '' : `ui-spinner--${safeSize}`, className].filter(Boolean).join(' ')
  return <span className={classes} role="status" aria-label={label} />
}
