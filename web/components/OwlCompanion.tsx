'use client'

import { usePathname } from 'next/navigation'
import { X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import OwlLogo from './OwlLogo'

const messages: Record<string, string> = {
  '/': 'Upload your resume to begin your journey.',
  '/upload': 'Take your time. I\'ll analyze everything.',
  '/clusters': 'You\'re a strong match for 3 clusters!',
  '/plan': 'Your plan is live. Week 1 is achievable.',
}

interface Props {
  onClose: () => void
}

export default function OwlCompanion({ onClose }: Props) {
  const pathname = usePathname()
  const message = messages[pathname] ?? messages['/']

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.95 }}
        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        style={{
          position: 'fixed',
          bottom: '96px',
          right: '24px',
          width: '260px',
          background: 'white',
          border: '1px solid #E8E6E1',
          borderRadius: '20px',
          padding: '20px',
          boxShadow: '0 16px 48px rgba(0,0,0,0.1)',
          zIndex: 60,
        }}
      >
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '12px',
            right: '12px',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: '#6B6B6B',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '4px',
            borderRadius: '4px',
          }}
        >
          <X size={14} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
          <motion.div
            animate={{ y: [0, -4, 0] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          >
            <OwlLogo size={36} />
          </motion.div>
          <span style={{ fontSize: '13px', fontWeight: 700, color: '#8B1A1A', letterSpacing: '-0.01em' }}>
            Lumia
          </span>
        </div>

        <p style={{ fontSize: '14px', color: '#6B6B6B', lineHeight: 1.6 }}>
          {message}
        </p>
      </motion.div>
    </AnimatePresence>
  )
}
