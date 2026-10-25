import { NextResponse, type NextRequest } from 'next/server'

const PROTECTED = ['/dashboard', '/projects', '/agents', '/settings', '/team']
const AUTH_ROUTES = ['/login']

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl
  const token = req.cookies.get('access_token')?.value
  const isAuthed = Boolean(token)

  /* Not logged in → trying to reach a protected page */
  if (!isAuthed && PROTECTED.some((p) => pathname.startsWith(p))) {
    const url = new URL('/login', req.url)
    url.searchParams.set('callbackUrl', pathname)
    return NextResponse.redirect(url)
  }

  /* Logged in → trying to reach /login */
  if (isAuthed && AUTH_ROUTES.some((p) => pathname === p)) {
    return NextResponse.redirect(new URL('/dashboard', req.url))
  }

  return NextResponse.next()
}

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
