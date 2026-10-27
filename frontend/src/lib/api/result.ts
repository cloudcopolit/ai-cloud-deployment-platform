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

/** Turn a fetch Response into an ApiResult, validating the body with `schema`. */
export async function toResult<T>(res: Response, schema: z.ZodType<T>): Promise<ApiResult<T>> {
  let body: unknown = null
  try {
    body = res.status === 204 ? null : await res.json()
  } catch {
    body = null
  }
  if (!res.ok) {
    const envelope = ErrorEnvelopeSchema.safeParse(body)
    return {
      ok: false,
      kind: kindFor(res.status),
      status: res.status,
      code: envelope.success ? envelope.data.error.code : `HTTP_${res.status}`,
      message: envelope.success ? envelope.data.error.message : `Request failed (${res.status}).`
    }
  }
  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    return {
      ok: false,
      kind: 'invalid',
      status: res.status,
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
