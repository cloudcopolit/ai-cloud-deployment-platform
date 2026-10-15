'use client'

import { useState } from 'react'
import { LogOut, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/axios-browser'
import { useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export function LogoutButton() {
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  async function handleLogout() {
    setLoading(true)
    try {
      await api.post(`${API_URL}/auth/logout`)
    } finally {
      router.push('/login')
    }
  }

  return (
    <Button variant="ghost" size="sm" onClick={handleLogout} disabled={loading}>
      {loading ? <Loader2 className="size-4 animate-spin" /> : <LogOut className="size-4" />}
      <span className="ml-2">Sign out</span>
    </Button>
  )
}
