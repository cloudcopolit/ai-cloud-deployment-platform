import { NextRequest } from 'next/server'
import { describe, expect, it } from 'vitest'

import { proxy } from './proxy'

function request(path: string, token?: string) {
  const req = new NextRequest(new URL(path, 'http://localhost:3000'))
  if (token) req.cookies.set('access_token', token)
  return req
}

function redirectTarget(res: Response) {
  const location = res.headers.get('location')
  return location ? new URL(location) : null
}

describe('proxy route protection', () => {
  it.each(['/dashboard', '/projects/42', '/settings', '/team'])(
    'redirects anonymous visitors from %s to /login with a callback',
    (path) => {
      const res = proxy(request(path))

      expect(res.status).toBe(307)
      const target = redirectTarget(res)
      expect(target?.pathname).toBe('/login')
      expect(target?.searchParams.get('callbackUrl')).toBe(path)
    }
  )

  it.each(['/', '/login', '/register'])('lets anonymous visitors open %s', (path) => {
    const res = proxy(request(path))

    expect(redirectTarget(res)).toBeNull()
    expect(res.headers.get('x-middleware-next')).toBe('1')
  })

  it('sends signed-in users away from /login to the dashboard', () => {
    const res = proxy(request('/login', 'token'))

    expect(res.status).toBe(307)
    expect(redirectTarget(res)?.pathname).toBe('/dashboard')
  })

  it('lets signed-in users open protected pages', () => {
    const res = proxy(request('/dashboard', 'token'))

    expect(redirectTarget(res)).toBeNull()
    expect(res.headers.get('x-middleware-next')).toBe('1')
  })
})
