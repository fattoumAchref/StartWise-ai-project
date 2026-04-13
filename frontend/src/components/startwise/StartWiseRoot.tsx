'use client'
/**
 * StartWiseRoot — Client wrapper for AppProvider + SecurityToast
 * Must be a client component because AppProvider uses WebSocket + useEffect.
 * Mounted inside RootLayout (Server Component) via this thin wrapper.
 */
import { AppProvider } from '@/context/AppContext'
import SecurityToast from '@/components/SecurityToast'
import { ReactNode } from 'react'

export default function StartWiseRoot({ children }: { children: ReactNode }) {
  return (
    <AppProvider>
      {children}
      <SecurityToast />
    </AppProvider>
  )
}
