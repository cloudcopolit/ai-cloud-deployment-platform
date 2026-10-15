import { cookies } from 'next/headers'
import { UserSchema, type User } from '@/lib/validations/auth'

/* Server-side calls may need a different address than the browser (e.g. http://backend:8000 in Docker). */
const API_URL =
  process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

/**
 * Server-side only. Forward the access_token cookie to FastAPI /auth/me.
 * Returns null if not authenticated.
 */


export async function getCurrentUser(): Promise<User | null> {
  const jar = await cookies()
  const token = jar.get('access_token')?.value
  if (!token) return null

  const res = await fetch(`${API_URL}/auth/me`, {
    headers: { Cookie: `access_token=${token}` },
    cache: 'no-store'
  })

  if (!res.ok) return null

  const json = await res.json()
  const parsed = UserSchema.safeParse(json)
  return parsed.success ? parsed.data : null
}
