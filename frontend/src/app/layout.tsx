import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'StartWise — Assistant CFO',
  description: 'Analyse financière autonome pour startups tunisiennes',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  )
}
