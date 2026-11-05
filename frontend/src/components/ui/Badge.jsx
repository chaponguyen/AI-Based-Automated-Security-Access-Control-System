const tones = new Set(['neutral', 'success', 'warning', 'danger', 'info'])

export default function Badge({ tone = 'neutral', className = '', children, ...props }) {
  const safeTone = tones.has(tone) ? tone : 'neutral'
  const classes = ['ui-badge', `ui-badge--${safeTone}`, className].filter(Boolean).join(' ')
  return <span {...props} className={classes}>{children}</span>
}
