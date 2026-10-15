import { describe, expect, it } from 'vitest'

import { ApiErrorSchema, TokenResponseSchema, UserSchema } from './auth'

/* Shape returned by the backend's GET /auth/me (UserRead). */
const backendUser = {
  id: '6f1c2a8e-4b7d-4c1e-9a53-2d8f0b6e7c11',
  github_user_id: '1001',
  name: 'Alice Owner',
  email: 'alice@example.com',
  avatar_url: 'https://avatars.githubusercontent.com/u/1001'
}

describe('UserSchema', () => {
  it('accepts the backend UserRead response', () => {
    expect(UserSchema.parse(backendUser)).toEqual(backendUser)
  })

  it('accepts users with a hidden email and no avatar', () => {
    const user = { ...backendUser, name: null, email: null, avatar_url: null }

    expect(UserSchema.parse(user)).toEqual(user)
  })

  it.each([
    ['id', 'not-a-uuid'],
    ['email', 'not-an-email'],
    ['avatar_url', 'not a url'],
    ['github_user_id', 1001]
  ])('rejects an invalid %s', (field, value) => {
    expect(UserSchema.safeParse({ ...backendUser, [field]: value }).success).toBe(false)
  })
})

describe('TokenResponseSchema', () => {
  it('defaults the token type to bearer', () => {
    expect(TokenResponseSchema.parse({ access_token: 'jwt' })).toEqual({
      access_token: 'jwt',
      token_type: 'bearer'
    })
  })
})

describe('ApiErrorSchema', () => {
  it('accepts a FastAPI validation error', () => {
    const error = {
      detail: [{ loc: ['body', 'github_user_id'], msg: 'Field required', type: 'missing' }]
    }

    expect(ApiErrorSchema.parse(error)).toEqual(error)
  })
})
