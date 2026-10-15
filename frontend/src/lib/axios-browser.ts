/* eslint-disable @next/next/no-location-assign-relative-destination */
'use client'

import axios, { AxiosError, type AxiosInstance } from 'axios'

export const api: AxiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
  withCredentials: true, // ← essential: sends access_token cookie
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    // No refresh endpoint in the backend → on 401, bounce to login
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)
