const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
  ['second', 1]
]

const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

/** "3 minutes ago" / "in 2 hours". Invalid input renders as an em dash, never as a guess. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return '—'
  const seconds = Math.round((then.getTime() - now.getTime()) / 1000)
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size || unit === 'second') {
      return rtf.format(Math.round(seconds / size), unit)
    }
  }
  return '—'
}

export function shortSha(sha: string): string {
  return sha.slice(0, 7)
}

/** First line of a commit message, bounded. Rendered as text, never as HTML. */
export function commitTitle(message: string, max = 90): string {
  const first = message.split('\n', 1)[0] ?? ''
  return first.length > max ? `${first.slice(0, max - 1)}…` : first
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || ms < 0) return '—'
  if (ms < 1000) return `${ms} ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)} s`
  const m = Math.floor(s / 60)
  return `${m} min ${Math.round(s % 60)} s`
}

const USD = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })

/** $18.50 — always two decimals, so small line items are not rounded away. */
export function formatUsd(amount: number): string {
  return USD.format(amount)
}
