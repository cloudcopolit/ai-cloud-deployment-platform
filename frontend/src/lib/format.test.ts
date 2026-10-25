import { describe, expect, it } from 'vitest'
import { commitTitle, formatDuration, formatRelative, formatUsd, shortSha } from './format'

describe('formatRelative', () => {
  const now = new Date('2026-10-25T12:00:00Z')
  it('formats past and future times', () => {
    expect(formatRelative('2026-10-25T11:57:00Z', now)).toBe('3 minutes ago')
    expect(formatRelative('2026-10-25T14:00:00Z', now)).toBe('in 2 hours')
    expect(formatRelative('2026-10-24T12:00:00Z', now)).toBe('yesterday')
  })
  it('never guesses on invalid input', () => {
    expect(formatRelative('not a date', now)).toBe('—')
  })
})

describe('commit helpers', () => {
  it('shortens SHAs and takes the first message line', () => {
    expect(shortSha('0d2fa8a27090beecd39d16472a1412dcf64df775')).toBe('0d2fa8a')
    expect(commitTitle('feat: x\n\nbody')).toBe('feat: x')
    expect(commitTitle('a'.repeat(200), 10)).toBe('aaaaaaaaa…')
  })
  it('keeps markup as plain text', () => {
    expect(commitTitle('<img src=x onerror=alert(1)>')).toBe('<img src=x onerror=alert(1)>')
  })
})

describe('formatDuration', () => {
  it('handles ms, seconds, minutes and missing values', () => {
    expect(formatDuration(250)).toBe('250 ms')
    expect(formatDuration(12_340)).toBe('12.3 s')
    expect(formatDuration(125_000)).toBe('2 min 5 s')
    expect(formatDuration(null)).toBe('—')
  })
})

describe('formatUsd', () => {
  it('keeps cents', () => {
    expect(formatUsd(18.5)).toBe('$18.50')
    expect(formatUsd(0.5)).toBe('$0.50')
    expect(formatUsd(1234)).toBe('$1,234.00')
  })
})
