import type { Metadata } from 'next'
import { Inter, Instrument_Serif, Dancing_Script } from 'next/font/google'
import './globals.css'
import ConditionalBottomNav from '@/components/ConditionalBottomNav'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const instrumentSerif = Instrument_Serif({
  subsets: ['latin'],
  weight: '400',
  style: ['normal', 'italic'],
  variable: '--font-instrument',
  display: 'swap',
})

const dancingScript = Dancing_Script({
  subsets: ['latin'],
  weight: ['400', '700'],
  variable: '--font-dancing',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Lumia — Career Intelligence',
  description: 'Lumia maps your resume against today\'s live job market and gives you a specific, weekly plan to get where you want to go.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${inter.variable} ${instrumentSerif.variable} ${dancingScript.variable}`}>
      <body style={{ background: '#F5F6F4', minHeight: '100vh' }}>
        {children}
        <ConditionalBottomNav />
      </body>
    </html>
  )
}
