import { cookies } from 'next/headers'

export interface CurrentUser {
  id: string
  githubId: string
  login: string
  name?: string
  email?: string
  avatarUrl?: string
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const jar = await cookies()
  const token = jar.get('access_token')?.value
  if (!token) return null

  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store'
  })

  if (!res.ok) return null
  return res.json()
}
