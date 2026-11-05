import EmptyState from './EmptyState.jsx'
import ErrorState from './ErrorState.jsx'
import Spinner from './Spinner.jsx'

function getRowKey(row, rowIndex, rowKey) {
  if (typeof rowKey === 'function') return rowKey(row, rowIndex)
  return row?.[rowKey] ?? rowIndex
}

export default function Table({
  columns = [],
  rows = [],
  rowKey = 'id',
  loading = false,
  error = '',
  onRetry,
  emptyTitle = 'Chưa có dữ liệu',
  emptyDescription = 'Dữ liệu sẽ xuất hiện ở đây khi có bản ghi phù hợp.',
  className = '',
  caption,
}) {
  if (loading) {
    return <div className="ui-table-state" role="status"><Spinner /> <span>Đang tải dữ liệu…</span></div>
  }
  if (error) return <ErrorState message={error} onRetry={onRetry} />
  if (rows.length === 0) return <EmptyState title={emptyTitle} description={emptyDescription} />

  const classes = ['ui-table-wrap', className].filter(Boolean).join(' ')
  return (
    <div className={classes}>
      <table className="ui-table">
        {caption && <caption>{caption}</caption>}
        <thead><tr>{columns.map((column) => (
          <th key={column.key} scope="col" className={column.className} style={column.align ? { textAlign: column.align } : undefined}>{column.label}</th>
        ))}</tr></thead>
        <tbody>{rows.map((row, rowIndex) => (
          <tr key={getRowKey(row, rowIndex, rowKey)}>{columns.map((column) => (
            <td key={column.key} className={column.className} style={column.align ? { textAlign: column.align } : undefined}>
              {column.render ? column.render(row, rowIndex) : row?.[column.key]}
            </td>
          ))}</tr>
        ))}</tbody>
      </table>
    </div>
  )
}
