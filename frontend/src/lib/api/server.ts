import { cookies } from 'next/headers'
import type { z } from 'zod'
import { OFFLINE, toResult, type ApiResult } from './result'

/* Server components call the API directly (http://backend:8000 inside Docker). */
const API_URL =
  process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

/** GET from the API on behalf of the signed-in user (cookie forwarded as a bearer token). */
export async function apiGet<T>(path: string, schema: z.ZodType<T>): Promise<ApiResult<T>> {
  const token = (await cookies()).get('access_token')?.value
  try {
    const res = await fetch(`${API_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: 'no-store'
    })
    return await toResult(res, schema)
  } catch {
    return OFFLINE
  }
}
