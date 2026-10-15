import axios from 'axios'
import { cookies } from 'next/headers'

/* Server-side calls may need a different address than the browser (e.g. http://backend:8000 in Docker). */
const API_URL =
  process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function apiServer() {
  const jar = await cookies()
  const token = jar.get('access_token')?.value

  return axios.create({
    baseURL: API_URL,
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  })
}
