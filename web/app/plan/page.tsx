'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { mockPlan } from '@/lib/mockData'

export default function PlanPage() {
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [expanded, setExpanded] = useState(false)

  const toggle = (key: string) => {
    setChecked((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const weekLabels = ['One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight']

  return (
    <div
      style={{
        background: '#F8F7F4',
        minHeight: '100vh',
        padding: '48px 24px 180px',
      }}
    >
      <div style={{ maxWidth: '720px', margin: '0 auto' }}>
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <p style={{
            fontSize: '12px',
            fontWeight: 500,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: '#C9A84C',
            marginBottom: '10px',
          }}>
            Your plan
          </p>
          <h1 style={{
            fontSize: 'clamp(2rem, 4vw, 2.75rem)',
            fontWeight: 700,
            letterSpacing: '-0.03em',
            color: '#1A1A1A',
            marginBottom: '8px',
          }}>
            {mockPlan.duration_weeks} weeks to {mockPlan.cluster}.
          </h1>
          <p style={{ fontSize: '16px', color: '#6B6B6B', marginBottom: '32px' }}>
            Based on your profile and today&apos;s live job market.
          </p>

          {/* Stat chips */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '56px' }}>
            {[
              { label: '3 skill gaps identified', dot: 'crimson' },
              { label: '12 jobs match today', dot: null },
              { label: '87% cluster fit', dot: 'gold' },
            ].map(({ label, dot }) => (
              <span
                key={label}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '13px',
                  fontWeight: 500,
                  color: dot === 'crimson' ? '#8B1A1A' : '#1A1A1A',
                  border: '1px solid #E8E6E1',
                  borderRadius: '9999px',
                  padding: '6px 14px',
                  background: 'white',
                }}
              >
                {dot && (
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: dot === 'crimson' ? '#8B1A1A' : '#C9A84C',
                      flexShrink: 0,
                    }}
                  />
                )}
                {label}
              </span>
            ))}
          </div>
        </motion.div>

        {/* Week sections */}
        {mockPlan.weeks.map((week, wi) => (
          <motion.div
            key={week.week}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: wi * 0.1 + 0.2 }}
            style={{ marginBottom: '48px' }}
          >
            <div style={{ position: 'relative', marginBottom: '24px' }}>
              <span
                style={{
                  position: 'absolute',
                  left: '-8px',
                  top: '-16px',
                  fontSize: '80px',
                  fontWeight: 800,
                  color: 'rgba(139,26,26,0.05)',
                  lineHeight: 1,
                  letterSpacing: '-0.04em',
                  userSelect: 'none',
                  pointerEvents: 'none',
                }}
              >
                {String(week.week).padStart(2, '0')}
              </span>
              <h2 style={{
                fontSize: '22px',
                fontWeight: 700,
                letterSpacing: '-0.02em',
                color: '#1A1A1A',
                position: 'relative',
              }}>
                Week {weekLabels[week.week - 1]}
              </h2>
            </div>

            <div
              style={{
                background: 'white',
                border: '1px solid #E8E6E1',
                borderRadius: '12px',
                overflow: 'hidden',
              }}
            >
              {week.actions.map((action, ai) => {
                const key = `${week.week}-${ai}`
                const isChecked = checked.has(key)
                return (
                  <div
                    key={ai}
                    onClick={() => toggle(key)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '14px',
                      padding: '16px 20px',
                      borderBottom: ai < week.actions.length - 1 ? '1px solid #E8E6E1' : 'none',
                      cursor: 'pointer',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = '#F8F7F4' }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'white' }}
                  >
                    {/* Checkbox */}
                    <div
                      style={{
                        width: '20px',
                        height: '20px',
                        borderRadius: '5px',
                        border: `2px solid ${isChecked ? '#8B1A1A' : '#D4D0C8'}`,
                        background: isChecked ? '#8B1A1A' : 'transparent',
                        flexShrink: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'all 0.15s',
                      }}
                    >
                      {isChecked && (
                        <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                          <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </div>

                    <span
                      style={{
                        flex: 1,
                        fontSize: '15px',
                        color: isChecked ? '#6B6B6B' : '#1A1A1A',
                        textDecoration: isChecked ? 'line-through' : 'none',
                        transition: 'all 0.15s',
                      }}
                    >
                      {action.task}
                    </span>

                    <span style={{ fontSize: '13px', color: '#6B6B6B', flexShrink: 0 }}>
                      {action.hours}h
                    </span>
                  </div>
                )
              })}
            </div>
          </motion.div>
        ))}

        {/* Expand remaining weeks */}
        <div style={{ marginBottom: '48px' }}>
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: 'none',
              border: '1px solid #E8E6E1',
              borderRadius: '8px',
              padding: '12px 20px',
              fontSize: '14px',
              color: '#6B6B6B',
              cursor: 'pointer',
              width: '100%',
              transition: 'border-color 0.2s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#8B1A1A' }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#E8E6E1' }}
          >
            {expanded ? 'Collapse' : `Show full ${mockPlan.duration_weeks}-week plan`}
          </button>

          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.35, ease: 'easeInOut' }}
                style={{ overflow: 'hidden' }}
              >
                <div style={{ paddingTop: '32px' }}>
                  {Array.from({ length: mockPlan.duration_weeks - mockPlan.weeks.length }, (_, i) => i + mockPlan.weeks.length + 1).map((w) => (
                    <div key={w} style={{ marginBottom: '32px' }}>
                      <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#1A1A1A', marginBottom: '16px', letterSpacing: '-0.02em' }}>
                        Week {weekLabels[w - 1]}
                      </h2>
                      <div style={{ background: 'white', border: '1px solid #E8E6E1', borderRadius: '12px', padding: '16px 20px' }}>
                        <p style={{ fontSize: '14px', color: '#6B6B6B' }}>Detailed tasks coming soon.</p>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Bottom action bar */}
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <button
            style={{
              background: '#8B1A1A',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              padding: '13px 28px',
              fontSize: '15px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background 0.2s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = '#B94040' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = '#8B1A1A' }}
          >
            Start Week 1
          </button>
          <button
            style={{
              background: 'none',
              border: 'none',
              fontSize: '14px',
              color: '#6B6B6B',
              cursor: 'pointer',
              textDecoration: 'underline',
              textUnderlineOffset: '3px',
            }}
          >
            Export plan as PDF
          </button>
        </div>
      </div>
    </div>
  )
}
