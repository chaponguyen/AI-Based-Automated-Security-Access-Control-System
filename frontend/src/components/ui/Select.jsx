export default function Select({ id, error, description, className = '', children, ...props }) {
  const classes = ['ui-select', className].filter(Boolean).join(' ')
  const describedBy = [description && `${id}-description`, error && `${id}-error`].filter(Boolean).join(' ') || undefined
  return (
    <select {...props} id={id} className={classes} aria-invalid={Boolean(error)} aria-describedby={describedBy}>
      {children}
    </select>
  )
}
