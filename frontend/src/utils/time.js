const VIETNAM_TIME_ZONE = 'Asia/Ho_Chi_Minh'

function makeFormatter(options) {
  return new Intl.DateTimeFormat('vi-VN', { timeZone: VIETNAM_TIME_ZONE, ...options })
}

const dateTimeFormatter = makeFormatter({
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
})
const dateFormatter = makeFormatter({ day: '2-digit', month: '2-digit', year: 'numeric' })
const timeFormatter = makeFormatter({ hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' })
const timezonePartsFormatter = new Intl.DateTimeFormat('en-CA', {
  timeZone: VIETNAM_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
})

function parseDate(value) {
  if (value === null || value === undefined || value === '') return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function getPart(parts, type) {
  return parts.find((part) => part.type === type)?.value || ''
}

export function formatDateTime(value) {
  const date = parseDate(value)
  if (!date) return '—'
  const parts = dateTimeFormatter.formatToParts(date)
  return `${getPart(parts, 'hour')}:${getPart(parts, 'minute')}:${getPart(parts, 'second')} ${getPart(parts, 'day')}/${getPart(parts, 'month')}/${getPart(parts, 'year')}`
}

export function formatDate(value) {
  const date = parseDate(value)
  if (!date) return '—'
  const parts = dateFormatter.formatToParts(date)
  return `${getPart(parts, 'day')}/${getPart(parts, 'month')}/${getPart(parts, 'year')}`
}

export function formatTime(value) {
  const date = parseDate(value)
  if (!date) return '—'
  const parts = timeFormatter.formatToParts(date)
  return `${getPart(parts, 'hour')}:${getPart(parts, 'minute')}:${getPart(parts, 'second')}`
}

function getTimezoneOffsetMilliseconds(timestamp) {
  const date = new Date(timestamp)
  const parts = timezonePartsFormatter.formatToParts(date)
  const localAsUtc = Date.UTC(
    Number(getPart(parts, 'year')),
    Number(getPart(parts, 'month')) - 1,
    Number(getPart(parts, 'day')),
    Number(getPart(parts, 'hour')),
    Number(getPart(parts, 'minute')),
    Number(getPart(parts, 'second')),
  )
  return localAsUtc - Math.floor(timestamp / 1000) * 1000
}

function createVietnamLocalDate(year, month, day, hour, minute, second, millisecond) {
  const targetLocalAsUtc = Date.UTC(year, month - 1, day, hour, minute, second, millisecond)
  let timestamp = targetLocalAsUtc
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const adjusted = targetLocalAsUtc - getTimezoneOffsetMilliseconds(timestamp)
    if (adjusted === timestamp) break
    timestamp = adjusted
  }
  const date = new Date(timestamp)
  return Number.isNaN(date.getTime()) ? null : date
}

export function dateInputBoundaryToISOString(value, endOfDay = false) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''))
  if (!match) return ''
  const [, yearText, monthText, dayText] = match
  const year = Number(yearText)
  const month = Number(monthText)
  const day = Number(dayText)
  const calendarDate = new Date(Date.UTC(year, month - 1, day))
  if (calendarDate.getUTCFullYear() !== year || calendarDate.getUTCMonth() !== month - 1 || calendarDate.getUTCDate() !== day) return ''
  const date = endOfDay
    ? createVietnamLocalDate(year, month, day, 23, 59, 59, 999)
    : createVietnamLocalDate(year, month, day, 0, 0, 0, 0)
  return date?.toISOString() || ''
}

export function getTodayDateInput(value = new Date()) {
  const date = parseDate(value)
  if (!date) return ''
  const parts = timezonePartsFormatter.formatToParts(date)
  return `${getPart(parts, 'year')}-${getPart(parts, 'month')}-${getPart(parts, 'day')}`
}
