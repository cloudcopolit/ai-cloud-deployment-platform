// WCAG 2.2 contrast checker for the design tokens (node scripts/contrast.mjs).
// Exits non-zero if a pair that the UI uses for text falls below its required ratio.
// Ratios: 4.5 normal text, 3.0 large text / UI components (WCAG 1.4.3, 1.4.11).

const hex = (h) => h.replace('#', '').match(/../g).map((x) => parseInt(x, 16) / 255)
const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
const luminance = (h) => {
  const [r, g, b] = hex(h).map(lin)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
export const contrast = (a, b) => {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (l1 + 0.05) / (l2 + 0.05)
}

// [foreground, background, required, where it is used]
export const PAIRS = [
  // raw brand colors, for the record (not all are used for text)
  ['#2F6BFF', '#FFFFFF', 4.5, 'brand blue text on white (raw)'],
  ['#FFFFFF', '#2F6BFF', 4.5, 'white text on brand blue button (raw)'],
  ['#19D3C5', '#FFFFFF', 3.0, 'brand teal on white (raw)'],
  ['#19D3C5', '#0B1220', 4.5, 'brand teal text on dark surface (raw)'],
  // tokens actually used for text and controls
  ['#1F5AE6', '#FFFFFF', 4.5, 'light: --primary text/links on background'],
  ['#FFFFFF', '#1F5AE6', 4.5, 'light: --primary-foreground on --primary'],
  ['#0B7F76', '#FFFFFF', 4.5, 'light: --accent-strong (teal text) on background'],
  ['#5C6B82', '#FFFFFF', 4.5, 'light: --muted-foreground on background'],
  ['#5C6B82', '#F3F6FA', 4.5, 'light: --muted-foreground on --muted'],
  ['#0B1220', '#FFFFFF', 4.5, 'light: --foreground on background'],
  ['#B42318', '#FFFFFF', 4.5, 'light: --destructive text'],
  ['#8A5300', '#FFFFFF', 4.5, 'light: --warning text'],
  ['#0F7A3D', '#FFFFFF', 4.5, 'light: --success text'],
  ['#7A8BA6', '#FFFFFF', 3.0, 'light: --border-strong (input borders, UI 1.4.11)'],
  ['#7AA2FF', '#0B1220', 4.5, 'dark: --primary text/links on background'],
  ['#0B1220', '#7AA2FF', 4.5, 'dark: --primary-foreground on --primary'],
  ['#19D3C5', '#0B1220', 4.5, 'dark: --accent-strong (teal text) on background'],
  ['#9AA8BD', '#0B1220', 4.5, 'dark: --muted-foreground on background'],
  ['#9AA8BD', '#162033', 4.5, 'dark: --muted-foreground on --card'],
  ['#E8EDF5', '#0B1220', 4.5, 'dark: --foreground on background'],
  ['#FF8A80', '#0B1220', 4.5, 'dark: --destructive text'],
  ['#F5B84A', '#0B1220', 4.5, 'dark: --warning text'],
  ['#4ADE80', '#0B1220', 4.5, 'dark: --success text'],
  ['#5A6A85', '#0B1220', 3.0, 'dark: --border-strong (UI 1.4.11)'],
]

const raw = new Set(PAIRS.slice(0, 4).map((p) => p[3]))
let failed = 0
for (const [fg, bg, need, where] of PAIRS) {
  const ratio = contrast(fg, bg)
  const ok = ratio >= need
  if (!ok && !raw.has(where)) failed++
  const tag = raw.has(where) ? (ok ? 'ok  ' : 'FAIL (raw, not used for this)') : ok ? 'ok  ' : 'FAIL'
  const shown = (Math.floor(ratio * 100) / 100).toFixed(2) // never round a failure up to a pass
  console.log(`${tag.padEnd(30)} ${shown.padStart(5)}:1 need ${need}  ${fg} on ${bg}  ${where}`)
}
if (failed) {
  console.error(`${failed} token pair(s) below WCAG 2.2 AA`)
  process.exit(1)
}
