import axios from 'axios'
import { cookies } from 'next/headers'
import type { z } from 'zod'
import { OFFLINE, resultFromResponse, type ApiResult } from './result'

/* Server components call the API directly (http://backend:8000 inside Docker). */
const API_URL =
  process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

const http = axios.create({
  baseURL: API_URL,
  timeout: 30_000,
  headers: { Accept: 'application/json' },
  validateStatus: () => true
})

/** GET from the API on behalf of the signed-in user (cookie forwarded as a bearer token). */
export async function apiGet<T>(path: string, schema: z.ZodType<T>): Promise<ApiResult<T>> {
  const token = (await cookies()).get('access_token')?.value
  try {
    const res = await http.get<unknown>(path, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined
    })
    return resultFromResponse(res.status, res.data, schema)
  } catch {
    return OFFLINE
  }
}
