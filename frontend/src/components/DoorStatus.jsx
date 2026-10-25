// Agent 3 — Đã khóa / đang mở + đếm ngược
export default function DoorStatus({ doorState }) {
  if (!doorState) return null

  const unlocked = doorState.lock === 'unlocked'
  const open = doorState.door === 'open'
  const label = open ? 'Cửa đang mở' : unlocked ? 'Đã mở khóa' : 'Đã khóa'

  return (
    <section className={`door-status ${open || unlocked ? 'door-status--open' : 'door-status--closed'}`} aria-live="polite">
      <span className="door-status__light" aria-hidden="true" />
      <div><strong>{label}</strong><small>{open ? 'Cảm biến cửa báo đang mở' : unlocked ? 'Khóa đang mở' : 'Cửa đang đóng và khóa'}</small></div>
    </section>
  )
}
