import { NextResponse, type NextRequest } from 'next/server'
import { jwtVerify } from 'jose' // Edge-compatible

const PROTECTED = ['/dashboard', '/settings', '/projects']
const AUTH_ROUTES = ['/login', '/register']

// Refresh if less than 60s of life left
const REFRESH_THRESHOLD_MS = 60_000

async function isExpiringSoon(token: string): Promise<boolean> {
  try {
    const secret = new TextEncoder().encode(process.env.NEXT_PUBLIC_JWT_SECRET!) // shared with FastAPI
    const { payload } = await jwtVerify(token, secret)
    const exp = (payload.exp ?? 0) * 1000
    return Date.now() > exp - REFRESH_THRESHOLD_MS
  } catch {
    return true // unparseable = treat as expired
  }
}

export async function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl
  const accessToken = req.cookies.get('access_token')?.value
  const refreshToken = req.cookies.get('refresh_token')?.value
  const isProtected = PROTECTED.some((p) => pathname.startsWith(p))
  console.log(pathname, isProtected)

  const res = NextResponse.next()

  /* ---------- 1. Proactive refresh ---------- */
  if (accessToken && refreshToken && (await isExpiringSoon(accessToken))) {
    const refreshRes = await fetch(`api/auth/refresh`, {
      method: 'POST',
      headers: {
        // Forward the refresh cookie — browser sent it to middleware
        Cookie: `refresh_token=${refreshToken}`
      }
    })

    if (refreshRes.ok) {
      // Forward FastAPI's Set-Cookie headers to the browser
      const setCookies = refreshRes.headers.getSetCookie()
      setCookies.forEach((c) => res.headers.append('Set-Cookie', c))
    } else {
      // Refresh failed → session dead
      res.cookies.delete('access_token')
      res.cookies.delete('refresh_token')

      if (isProtected) {
        const url = new URL('/login', req.url)
        url.searchParams.set('callbackUrl', pathname)
        return NextResponse.redirect(url)
      }
    }
  }

  /* ---------- 2. Route guards ---------- */
  const isAuthed = Boolean(res.cookies.get('access_token')?.value ?? accessToken)

  if (!isAuthed && isProtected) {
    const url = new URL('/login', req.url)
    url.searchParams.set('callbackUrl', pathname)
    return NextResponse.redirect(url)
  }

  if (isAuthed && AUTH_ROUTES.some((p) => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL('/dashboard', req.url))
  }

  return res
}

// Add this at the bottom of middleware.ts
export const config = {
  matcher: [
    /*
     * Match all request paths EXCEPT for the ones starting with:
     * - api (Next.js API routes)
     * - _next/static (static files like CSS/JS)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!api|_next/data|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|\\.well-known).*)'
  ]
}
