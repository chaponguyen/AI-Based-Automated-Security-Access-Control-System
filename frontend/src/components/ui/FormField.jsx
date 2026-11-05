export default function FormField({ id, label, description, error, required = false, className = '', children }) {
  const classes = ['ui-field', className].filter(Boolean).join(' ')
  return (
    <div className={classes}>
      <label className="ui-field__label" htmlFor={id}>
        {label}
        {required && <span className="ui-field__required" aria-hidden="true">*</span>}
      </label>
      {children}
      {description && <small className="ui-field__description" id={`${id}-description`}>{description}</small>}
      {error && <small className="ui-field__error" id={`${id}-error`} role="alert">{error}</small>}
    </div>
  )
}
