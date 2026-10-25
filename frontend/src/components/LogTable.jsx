// Agent 3 — Bảng nhật ký dùng chung
import { getReasonLabel } from '../services/reasons.js'

function formatTimestamp(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('vi-VN')
}

export default function LogTable({ rows = [] }) {
  return (
    <div className="table-wrap">
      <table className="logs-table">
        <thead>
          <tr><th>Thời gian</th><th>Tên</th><th>Độ giống</th><th>Chống giả mạo</th><th>Kết quả</th><th>Lý do</th></tr>
        </thead>
        <tbody>{rows.map((row, index) => (
          <tr key={`${row.timestamp}-${row.name}-${index}`}>
            <td>{formatTimestamp(row.timestamp)}</td>
            <td>{row.name || 'Không xác định'}</td>
            <td>{typeof row.similarity === 'number' ? row.similarity.toFixed(2) : '—'}</td>
            <td>{row.liveness === true ? 'Đạt' : row.liveness === false ? 'Không đạt' : '—'}</td>
            <td><span className={`result-chip ${row.decision === 'granted' ? 'result-chip--good' : 'result-chip--bad'}`}>{row.decision === 'granted' ? 'Cho phép' : 'Từ chối'}</span></td>
            <td>{getReasonLabel(row.reason)}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}
