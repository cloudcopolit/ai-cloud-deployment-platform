'use client'

import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true
})

// Single-flight refresh: if 5 requests hit 401 at once, only 1 refresh call fires
let refreshing: Promise<void> | null = null

async function refreshSession() {
  if (!refreshing) {
    refreshing = axios
      .post(`${API_URL}/auth/refresh`, null, { withCredentials: true })
      .then(() => undefined)
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retried?: boolean }

    if (
      error.response?.status === 401 &&
      !original._retried &&
      !original.url?.includes('/auth/refresh') &&
      typeof window !== 'undefined'
    ) {
      original._retried = true
      try {
        await refreshSession()
        return api(original) // retry
      } catch {
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)
