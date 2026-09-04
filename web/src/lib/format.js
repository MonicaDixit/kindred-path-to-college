import dayjs from 'dayjs'

export const pct = (v, digits = 0) =>
  v == null ? '—' : `${(v * 100).toFixed(digits)}%`

export const money = (v) =>
  v == null ? '—' : `$${Number(v).toLocaleString()}`

export const dateLabel = (iso) =>
  iso ? dayjs(iso).format('MMM D, YYYY') : '—'

export const daysUntil = (iso) =>
  iso ? dayjs(iso).startOf('day').diff(dayjs().startOf('day'), 'day') : null

export function selectivityLabel(rate) {
  if (rate == null) return 'Unknown'
  if (rate < 0.1) return 'Most selective'
  if (rate < 0.2) return 'Highly selective'
  if (rate < 0.4) return 'Selective'
  if (rate < 0.6) return 'Moderately selective'
  return 'Accessible'
}

export const MAJORS = [
  'Computer Science', 'Engineering', 'Business', 'Physics', 'Chemistry',
  'Biology', 'Pre-Med', 'Mathematics', 'Economics', 'Liberal Arts',
]
