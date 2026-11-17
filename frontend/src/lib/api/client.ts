/* eslint-disable @next/next/no-location-assign-relative-destination */
'use client'

import axios, { isAxiosError, isCancel, type AxiosRequestConfig } from 'axios'
import type { z } from 'zod'
import { OFFLINE, resultFromResponse, type ApiResult } from './result'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

/** Shared browser client: sends the auth cookie cross-origin and never throws on HTTP status. */
export const http = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  timeout: 30_000,
  headers: { Accept: 'application/json' },
  validateStatus: () => true
})

type ApiInit = {
  method?: AxiosRequestConfig['method']
  body?: unknown
  signal?: AbortSignal
  headers?: Record<string, string>
}

/**
 * Browser-side API call with the auth cookie. Never throws except on cancellation (so callers
 * can ignore aborted requests); every other outcome is an ApiResult.
 */
export async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  init: ApiInit = {}
): Promise<ApiResult<T>> {
  try {
    const res = await http.request<unknown>({
      url: path,
      method: init.method ?? 'GET',
      data: init.body,
      headers: init.headers,
      signal: init.signal
    })
    if (
      res.status === 401 &&
      typeof window !== 'undefined' &&
      window.location.pathname !== '/login'
    ) {
      // A full reload drops every piece of client state that belonged to the ended session.
      window.location.assign('/login')
    }
    return resultFromResponse(res.status, res.data, schema)
  } catch (err) {
    if (isCancel(err)) throw err
    if (isAxiosError(err) && err.response)
      return resultFromResponse(err.response.status, err.response.data, schema)
    return OFFLINE
  }
}
