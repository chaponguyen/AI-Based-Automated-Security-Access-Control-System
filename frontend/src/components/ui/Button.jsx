import Spinner from './Spinner.jsx'

const variants = new Set(['primary', 'secondary', 'danger', 'ghost'])
const sizes = new Set(['sm', 'md', 'lg'])

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  type = 'button',
  className = '',
  children,
  ...props
}) {
  const safeVariant = variants.has(variant) ? variant : 'primary'
  const safeSize = sizes.has(size) ? size : 'md'
  const classes = ['ui-button', `ui-button--${safeVariant}`, `ui-button--${safeSize}`, className]
    .filter(Boolean)
    .join(' ')

  return (
    <button
      {...props}
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading && <Spinner size="sm" className="ui-button__spinner" />}
      {children}
    </button>
  )
}
