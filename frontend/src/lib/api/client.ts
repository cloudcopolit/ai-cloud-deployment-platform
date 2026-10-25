'use client'

import type { z } from 'zod'
import { OFFLINE, toResult, type ApiResult } from './result'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

/** Browser-side API call with the auth cookie. Never throws; returns an ApiResult. */
export async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  init: { method?: string; body?: unknown; signal?: AbortSignal; headers?: Record<string, string> } = {}
): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method: init.method ?? 'GET',
      credentials: 'include',
      headers: {
        ...(init.body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...init.headers
      },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      signal: init.signal
    })
    if (res.status === 401 && typeof window !== 'undefined' && window.location.pathname !== '/login') {
      // A full reload drops every piece of client state that belonged to the ended session.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign('/login')
    }
    return await toResult(res, schema)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    return OFFLINE
  }
}
