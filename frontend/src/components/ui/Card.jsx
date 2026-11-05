export default function Card({ as: Component = 'section', padding = 'md', className = '', children, ...props }) {
  const safePadding = ['sm', 'md', 'lg'].includes(padding) ? padding : 'md'
  const classes = ['ui-card', `ui-card--padding-${safePadding}`, className].filter(Boolean).join(' ')
  return <Component {...props} className={classes}>{children}</Component>
}
