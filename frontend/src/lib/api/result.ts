import type { z } from 'zod'
import { ErrorEnvelopeSchema } from './schemas'

/** Outcome of an API call. Pages render every failure kind explicitly. */
export type ApiResult<T> =
  | { ok: true; data: T }
  | {
      ok: false
      kind: 'offline' | 'unauthenticated' | 'forbidden' | 'not_found' | 'invalid' | 'error'
      status: number
      code: string
      message: string
    }

export type ApiFailure = Extract<ApiResult<never>, { ok: false }>

function kindFor(status: number): ApiFailure['kind'] {
  if (status === 401) return 'unauthenticated'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'not_found'
  return 'error'
}

/**
 * Turn an HTTP status and an already-parsed body into an ApiResult.
 * Error bodies are read through the API error envelope; success bodies are validated with `schema`.
 */
export function resultFromResponse<T>(
  status: number,
  body: unknown,
  schema: z.ZodType<T>
): ApiResult<T> {
  if (status < 200 || status >= 300) {
    const envelope = ErrorEnvelopeSchema.safeParse(body)
    return {
      ok: false,
      kind: kindFor(status),
      status,
      code: envelope.success ? envelope.data.error.code : `HTTP_${status}`,
      message: envelope.success ? envelope.data.error.message : `Request failed (${status}).`
    }
  }
  const parsed = schema.safeParse(status === 204 ? null : body)
  if (!parsed.success) {
    return {
      ok: false,
      kind: 'invalid',
      status,
      code: 'UNEXPECTED_RESPONSE',
      message: 'The server answered in an unexpected format.'
    }
  }
  return { ok: true, data: parsed.data }
}

export const OFFLINE: ApiFailure = {
  ok: false,
  kind: 'offline',
  status: 0,
  code: 'BACKEND_UNREACHABLE',
  message: 'The CloudPilot API cannot be reached.'
}
