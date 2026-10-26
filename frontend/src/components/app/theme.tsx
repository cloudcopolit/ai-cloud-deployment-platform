'use client'

import { Monitor, Moon, Sun } from 'lucide-react'
import { ThemeProvider as NextThemes, useTheme } from 'next-themes'
import { useSyncExternalStore } from 'react'

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemes attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      {children}
    </NextThemes>
  )
}

const OPTIONS = [
  { value: 'light', label: 'Light theme', Icon: Sun },
  { value: 'dark', label: 'Black theme', Icon: Moon },
  { value: 'system', label: 'System theme', Icon: Monitor }
] as const

const subscribe = () => () => {}

/** Three-way theme switch; rendered as a radio group so screen readers announce the choice. */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  // next-themes only knows the theme after hydration
  const mounted = useSyncExternalStore(subscribe, () => true, () => false)
  return (
    <div role="radiogroup" aria-label="Color theme" className="flex rounded-lg border p-0.5">
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = mounted && theme === value
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            onClick={() => setTheme(value)}
            className={`rounded-md p-1.5 ${active ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
          >
            <Icon className="size-4" aria-hidden />
          </button>
        )
      })}
    </div>
  )
}
