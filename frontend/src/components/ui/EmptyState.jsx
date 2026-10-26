export default function EmptyState({ title = 'Chưa có dữ liệu', description, action, className = '' }) {
  const classes = ['ui-empty-state', className].filter(Boolean).join(' ')
  return (
    <div className={classes} role="status">
      <span className="ui-empty-state__mark" aria-hidden="true">—</span>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  )
}
