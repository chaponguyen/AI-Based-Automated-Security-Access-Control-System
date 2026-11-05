export default function Input({ id, error, description, className = '', ...props }) {
  const classes = ['ui-input', className].filter(Boolean).join(' ')
  const describedBy = [description && `${id}-description`, error && `${id}-error`].filter(Boolean).join(' ') || undefined
  return <input {...props} id={id} className={classes} aria-invalid={Boolean(error)} aria-describedby={describedBy} />
}
