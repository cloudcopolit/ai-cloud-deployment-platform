import { z } from 'zod'

/* Matches backend UserRead */
export const UserSchema = z.object({
  id: z.uuid(),
  github_user_id: z.string(),
  name: z.string().nullable(),
  email: z.email().nullable(),
  avatar_url: z.url().nullable()
})

export type User = z.infer<typeof UserSchema>

/* Matches backend TokenResponse (used by /auth/dev-login) */
export const TokenResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string().default('bearer')
})

export type TokenResponse = z.infer<typeof TokenResponseSchema>

/* Matches backend HTTPValidationError */
export const ApiErrorSchema = z.object({
  detail: z
    .array(
      z.object({
        loc: z.array(z.union([z.string(), z.number()])),
        msg: z.string(),
        type: z.string()
      })
    )
    .optional()
})

export type ApiError = z.infer<typeof ApiErrorSchema>
