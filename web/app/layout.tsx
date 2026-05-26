import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import BottomNav from '@/components/BottomNav'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Lumia — Career Intelligence',
  description: 'Know exactly where you stand. Lumia maps your resume against today\'s live job market.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body style={{ background: '#F8F7F4', minHeight: '100vh' }}>
        {children}
        <BottomNav />
      </body>
    </html>
  )
}
