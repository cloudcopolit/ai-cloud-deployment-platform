'use client'

import { useEffect, useRef } from 'react'

/**
 * Calls `tick` until it returns true ("done"). Starts at `intervalMs`, backs off ×1.5 up to
 * `maxMs` while nothing changes, and pauses while the tab is hidden (ADR-016: polling).
 * `tick` returns { done, changed }.
 */
export function usePoll(
  tick: (signal: AbortSignal) => Promise<{ done: boolean; changed: boolean }>,
  { intervalMs = 1500, maxMs = 6000, enabled = true }: { intervalMs?: number; maxMs?: number; enabled?: boolean } = {}
) {
  const tickRef = useRef(tick)
  useEffect(() => {
    tickRef.current = tick
  }, [tick])

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    let delay = intervalMs
    let stopped = false

    const schedule = () => {
      if (stopped) return
      timer = setTimeout(run, document.hidden ? Math.max(delay, maxMs) : delay)
    }
    const run = async () => {
      if (document.hidden) return schedule()
      try {
        const { done, changed } = await tickRef.current(controller.signal)
        if (done) {
          stopped = true
          return
        }
        delay = changed ? intervalMs : Math.min(maxMs, Math.round(delay * 1.5))
      } catch {
        if (controller.signal.aborted) return
        delay = Math.min(maxMs, Math.round(delay * 1.5))
      }
      schedule()
    }
    schedule()
    return () => {
      stopped = true
      controller.abort()
      if (timer) clearTimeout(timer)
    }
  }, [enabled, intervalMs, maxMs])
}
