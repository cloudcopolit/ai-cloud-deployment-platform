import { isAxiosError } from 'axios'

/** Message from the backend error envelope (`{ error: { message } }`), or the fallback. */
export function apiErrorMessage(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const data = err.response?.data as { error?: { message?: unknown }; detail?: unknown } | undefined
    if (typeof data?.error?.message === 'string') return data.error.message
    if (typeof data?.detail === 'string') return data.detail
  }
  return fallback
}
