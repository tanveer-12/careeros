'use client'

import { useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { TrendingUp, FileText, Map, Bird } from 'lucide-react'
import OwlCompanion from './OwlCompanion'

const tabs = [
  { id: 'market', label: 'Market', icon: TrendingUp, href: '/#market' },
  { id: 'resume', label: 'Resume', icon: FileText, href: '/upload' },
  { id: 'plan', label: 'Plan', icon: Map, href: '/plan' },
  { id: 'lumia', label: 'Lumia', icon: Bird, href: null },
]

export default function BottomNav() {
  const router = useRouter()
  const pathname = usePathname()
  const [owlOpen, setOwlOpen] = useState(false)

  const getActiveTab = () => {
    if (pathname === '/upload') return 'resume'
    if (pathname === '/plan') return 'plan'
    if (pathname === '/clusters') return 'market'
    return 'market'
  }

  const activeTab = getActiveTab()

  const handleTabClick = (tab: typeof tabs[0]) => {
    if (tab.id === 'lumia') {
      setOwlOpen(!owlOpen)
      return
    }
    if (tab.href) {
      if (tab.href.startsWith('/#')) {
        router.push('/')
        setTimeout(() => {
          const el = document.getElementById(tab.href!.slice(2))
          el?.scrollIntoView({ behavior: 'smooth' })
        }, 100)
      } else {
        router.push(tab.href)
      }
    }
  }

  return (
    <>
      {owlOpen && <OwlCompanion onClose={() => setOwlOpen(false)} />}
      <nav
        style={{
          position: 'fixed',
          bottom: '24px',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 50,
          background: 'rgba(255,255,255,0.85)',
          backdropFilter: 'blur(12px)',
          border: '1px solid #E8E6E1',
          borderRadius: '9999px',
          padding: '10px 24px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.08)',
          display: 'flex',
          gap: '8px',
          alignItems: 'center',
        }}
      >
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          const isOwl = tab.id === 'lumia'
          return (
            <button
              key={tab.id}
              onClick={() => handleTabClick(tab)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '4px',
                padding: '8px 16px',
                borderRadius: '9999px',
                border: 'none',
                background: isOwl && owlOpen ? '#F0E4C2' : 'transparent',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                minWidth: '64px',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = '#F0E4C2'
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive && !(isOwl && owlOpen)) {
                  e.currentTarget.style.background = 'transparent'
                }
              }}
            >
              <Icon
                size={18}
                color={isActive || (isOwl && owlOpen) ? '#8B1A1A' : '#6B6B6B'}
                strokeWidth={isActive ? 2.5 : 1.5}
              />
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: isActive ? 600 : 400,
                  color: isActive || (isOwl && owlOpen) ? '#8B1A1A' : '#6B6B6B',
                  letterSpacing: '0.02em',
                }}
              >
                {tab.label}
              </span>
              {isActive && (
                <div
                  style={{
                    width: '4px',
                    height: '4px',
                    borderRadius: '50%',
                    background: '#8B1A1A',
                    marginTop: '-2px',
                  }}
                />
              )}
            </button>
          )
        })}
      </nav>
    </>
  )
}
