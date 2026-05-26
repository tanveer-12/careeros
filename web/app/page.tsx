'use client'

import { useRef } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { Upload, Target, Calendar } from 'lucide-react'
import OwlLogo from '@/components/OwlLogo'

const steps = [
  {
    num: '01',
    title: 'Upload your resume',
    icon: Upload,
    caption: 'We parse your resume and extract your skills, experience, and signals.',
  },
  {
    num: '02',
    title: 'See where you fit',
    icon: Target,
    caption: 'Your profile is mapped against live job clusters across all industries.',
  },
  {
    num: '03',
    title: 'Get your plan',
    icon: Calendar,
    caption: 'A week-by-week execution plan built specifically for your gaps and goals.',
    gold: true,
  },
]

const tickerItems = [
  'Software Engineering', 'Financial Analysis', 'Mechanical Engineering',
  'Clinical Research', 'Product Management', 'Data Engineering',
  'UX Design', 'Business Intelligence', 'DevOps', 'Marketing Analytics',
]

export default function LandingPage() {
  const router = useRouter()
  const howRef = useRef<HTMLElement>(null)

  return (
    <div style={{ background: '#F8F7F4' }}>
      {/* Hero Section */}
      <section
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
        }}
      >
        {/* Top nav */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '24px 48px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <OwlLogo size={32} />
            <span style={{ fontSize: '18px', fontWeight: 700, color: '#1A1A1A', letterSpacing: '-0.03em' }}>
              Lumia
            </span>
          </div>
          <button
            style={{
              background: 'none',
              border: 'none',
              fontSize: '14px',
              color: '#6B6B6B',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            Sign in
          </button>
        </div>

        {/* Hero content */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
            padding: '0 24px 120px',
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0 }}
          >
            <span
              style={{
                display: 'inline-block',
                fontSize: '12px',
                fontWeight: 500,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: '#C9A84C',
                background: '#F0E4C2',
                padding: '5px 14px',
                borderRadius: '9999px',
                marginBottom: '32px',
              }}
            >
              Career Intelligence
            </span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            style={{
              fontSize: 'clamp(3rem, 6vw, 5rem)',
              fontWeight: 700,
              letterSpacing: '-0.04em',
              color: '#1A1A1A',
              lineHeight: 1.08,
              marginBottom: '24px',
              maxWidth: '800px',
            }}
          >
            Know exactly where<br />you stand.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            style={{
              fontSize: '1.2rem',
              color: '#6B6B6B',
              maxWidth: '520px',
              lineHeight: 1.7,
              marginBottom: '40px',
            }}
          >
            Lumia maps your resume against today&apos;s live job market and gives you a specific,
            weekly plan to get where you want to go.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, delay: 0.3 }}
            style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}
          >
            <button
              onClick={() => router.push('/upload')}
              style={{
                background: '#8B1A1A',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                padding: '14px 32px',
                fontSize: '16px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                letterSpacing: '-0.01em',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#B94040'
                e.currentTarget.style.transform = 'scale(1.02)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = '#8B1A1A'
                e.currentTarget.style.transform = 'scale(1)'
              }}
            >
              Upload your resume
            </button>
            <span style={{ fontSize: '13px', color: '#6B6B6B' }}>
              No account required to start.
            </span>
          </motion.div>
        </div>
      </section>

      {/* How It Works */}
      <section
        id="market"
        ref={howRef}
        style={{
          padding: '100px 48px',
          maxWidth: '1100px',
          margin: '0 auto',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '64px' }}>
          <p style={{
            fontSize: '12px',
            fontWeight: 500,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: '#C9A84C',
            marginBottom: '16px',
          }}>
            How it works
          </p>
          <h2 style={{
            fontSize: 'clamp(2rem, 4vw, 3rem)',
            fontWeight: 700,
            letterSpacing: '-0.03em',
            color: '#1A1A1A',
          }}>
            Three steps to clarity.
          </h2>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '2px',
          position: 'relative',
        }}>
          {steps.map((step, i) => {
            const Icon = step.icon
            return (
              <motion.div
                key={step.num}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-60px' }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                style={{
                  background: 'white',
                  border: '1px solid #E8E6E1',
                  borderRadius: '16px',
                  padding: '40px 32px',
                  position: 'relative',
                  overflow: 'hidden',
                  margin: '1px',
                }}
              >
                <span
                  style={{
                    position: 'absolute',
                    top: '16px',
                    right: '24px',
                    fontSize: '72px',
                    fontWeight: 800,
                    color: step.gold ? 'rgba(201,168,76,0.08)' : 'rgba(139,26,26,0.06)',
                    lineHeight: 1,
                    letterSpacing: '-0.04em',
                    userSelect: 'none',
                  }}
                >
                  {step.num}
                </span>

                <div
                  style={{
                    width: '44px',
                    height: '44px',
                    borderRadius: '10px',
                    background: step.gold ? '#F0E4C2' : 'rgba(139,26,26,0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '24px',
                  }}
                >
                  <Icon size={20} color={step.gold ? '#C9A84C' : '#8B1A1A'} />
                </div>

                <h3 style={{
                  fontSize: '18px',
                  fontWeight: 700,
                  color: '#1A1A1A',
                  letterSpacing: '-0.02em',
                  marginBottom: '12px',
                }}>
                  {step.title}
                </h3>
                <p style={{ fontSize: '15px', color: '#6B6B6B', lineHeight: 1.7 }}>
                  {step.caption}
                </p>
              </motion.div>
            )
          })}
        </div>
      </section>

      {/* Market Ticker */}
      <div
        style={{
          background: 'white',
          borderTop: '1px solid #E8E6E1',
          borderBottom: '1px solid #E8E6E1',
          padding: '16px 0',
          overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', width: 'max-content' }} className="animate-ticker">
          {[...tickerItems, ...tickerItems].map((item, i) => (
            <span key={i} style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <span style={{ fontSize: '13px', fontFamily: 'monospace', color: '#6B6B6B', whiteSpace: 'nowrap', padding: '0 24px' }}>
                {item}
              </span>
              <span style={{ color: '#8B1A1A', fontSize: '10px' }}>·</span>
            </span>
          ))}
        </div>
      </div>

      {/* Final CTA */}
      <section style={{ textAlign: 'center', padding: '120px 24px 200px' }}>
        <h2 style={{
          fontSize: 'clamp(2rem, 4vw, 3rem)',
          fontWeight: 700,
          letterSpacing: '-0.03em',
          color: '#1A1A1A',
          marginBottom: '32px',
        }}>
          Ready to find your path?
        </h2>
        <button
          onClick={() => router.push('/upload')}
          style={{
            background: '#8B1A1A',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            padding: '14px 32px',
            fontSize: '16px',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            marginBottom: '12px',
            display: 'block',
            margin: '0 auto 12px',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = '#B94040' }}
          onMouseLeave={(e) => { e.currentTarget.style.background = '#8B1A1A' }}
        >
          Start with your resume →
        </button>
        <p style={{ fontSize: '13px', color: '#6B6B6B', marginTop: '12px' }}>
          Takes about 2 minutes.
        </p>
      </section>
    </div>
  )
}
