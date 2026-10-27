'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2, LogOut } from 'lucide-react'

import { Button } from '@/components/ui/button'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export function LogoutButton() {
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  async function handleLogout() {
    setLoading(true)
    try {
      await fetch(`${API_URL}/auth/logout`, { method: 'POST', credentials: 'include' })
    } finally {
      router.push('/login')
    }
  }

  return (
    <Button variant="ghost" size="icon" onClick={handleLogout} disabled={loading} aria-label="Sign out" title="Sign out">
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <LogOut className="size-4" aria-hidden />}
    </Button>
  )
}
