import { AxiosError, AxiosHeaders } from 'axios'
import { describe, expect, it } from 'vitest'
import { apiErrorMessage } from './api-error'

function axiosErrorWith(data: unknown): AxiosError {
  const err = new AxiosError('Request failed')
  err.response = {
    data,
    status: 400,
    statusText: 'Bad Request',
    headers: {},
    config: { headers: new AxiosHeaders() }
  }
  return err
}

describe('apiErrorMessage', () => {
  it('reads the error envelope message', () => {
    expect(apiErrorMessage(axiosErrorWith({ error: { message: 'Plan limit' } }), 'x')).toBe('Plan limit')
  })
  it('falls back to a string detail', () => {
    expect(apiErrorMessage(axiosErrorWith({ detail: 'Not found' }), 'x')).toBe('Not found')
  })
  it('uses the fallback for non-axios errors and non-string messages', () => {
    expect(apiErrorMessage(new Error('boom'), 'fallback')).toBe('fallback')
    expect(apiErrorMessage(axiosErrorWith({ error: { message: 42 } }), 'fallback')).toBe('fallback')
  })
})
