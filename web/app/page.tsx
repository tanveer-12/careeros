'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion, useInView, useScroll, useTransform } from 'framer-motion'
import { ChevronDown } from 'lucide-react'

// ─── Design tokens ───────────────────────────────────────────────────────────

const C = {
  base:          '#F5F6F4',
  surface:       '#FFFFFF',
  dark:          '#0D1F1F',
  textPrimary:   '#0D1F1F',
  textSecondary: '#4A6670',
  brand:         '#0A7C6E',
  brandHover:    '#0D9B8A',
  gold:          '#C9873A',
  goldSubtle:    'rgba(201,135,58,0.12)',
} as const

const EASE = [0.22, 1, 0.36, 1] as const

// ─── Data ────────────────────────────────────────────────────────────────────

const PROBLEM_LINES = [
  "You don't know which skills actually matter.",
  'You apply to roles and hear nothing back.',
  'Nobody tells you what to do next.',
]

const TICKER_ITEMS = [
  'Software Engineering', 'Financial Analysis', 'Mechanical Engineering',
  'Clinical Research', 'Product Management', 'Data Engineering',
  'UX Design', 'Business Intelligence', 'DevOps', 'Marketing Analytics',
]

const DOMAIN_BARS = [
  { label: 'Software Eng', pct: 23 },
  { label: 'Finance',      pct: 11 },
  { label: 'Healthcare',   pct: 9  },
  { label: 'Engineering',  pct: 7  },
  { label: 'Consulting',   pct: 6  },
]

const HOW_STEPS = [
  {
    num: '01',
    title: 'Upload your resume.',
    body:  'Drop your resume. We extract your skills, experience signals, and career trajectory.',
  },
  {
    num: '02',
    title: 'See where you fit.',
    body:  'Your profile is mapped against live job clusters across every industry.',
  },
  {
    num: '03',
    title: 'Get your plan.',
    body:  'A week-by-week execution plan built specifically for your gaps and goals.',
  },
]

// ─── Navbar ──────────────────────────────────────────────────────────────────

function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const router = useRouter()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const letters = ['L', 'U', 'M', 'I', 'A']

  return (
    <nav style={{
      position:       'fixed',
      top:            0,
      left:           0,
      right:          0,
      zIndex:         50,
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'space-between',
      padding:        '0 clamp(24px, 5vw, 56px)',
      height:         '68px',
      transition:     'background 0.35s ease, backdrop-filter 0.35s ease, border-color 0.35s ease',
      background:     scrolled ? 'rgba(245,246,244,0.92)' : 'transparent',
      backdropFilter: scrolled ? 'blur(20px)'             : 'none',
      borderBottom:   scrolled ? '1px solid rgba(13,31,31,0.06)' : '1px solid transparent',
    }}>
      {/* Wordmark */}
      <div
        style={{ display: 'flex', gap: '1px', cursor: 'pointer', alignItems: 'baseline' }}
        onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      >
        {letters.map((l, i) => (
          <motion.span
            key={i}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 + i * 0.07 }}
            style={{
              fontSize:   '19px',
              fontWeight: 700,
              letterSpacing: '0.06em',
              color:      scrolled ? C.textPrimary : '#FFFFFF',
              transition: 'color 0.35s ease',
            }}
          >
            {l}
          </motion.span>
        ))}
      </div>

      {/* Center links */}
      <div style={{ display: 'flex', gap: '32px' }}>
        {([
          { label: 'Home',     target: 'top'           },
          { label: 'Explore',  target: 'how-it-works'  },
          { label: 'About',    target: 'market-signal' },
          { label: 'Reach Us', target: 'cta'           },
        ] as { label: string; target: string }[]).map(({ label, target }) => (
          <button
            key={label}
            onClick={() => {
              if (target === 'top') { window.scrollTo({ top: 0, behavior: 'smooth' }); return }
              document.getElementById(target)?.scrollIntoView({ behavior: 'smooth' })
            }}
            style={{
              background:  'none',
              border:      'none',
              fontSize:    '14px',
              fontWeight:  400,
              cursor:      'pointer',
              color:       scrolled ? C.textSecondary : 'rgba(255,255,255,0.60)',
              transition:  'color 0.25s ease',
              fontFamily:  'inherit',
              padding:     '4px 0',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = scrolled ? C.textPrimary : '#FFFFFF' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = scrolled ? C.textSecondary : 'rgba(255,255,255,0.60)' }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* CTA */}
      <button
        onClick={() => router.push('/upload')}
        style={{
          padding:       '9px 22px',
          borderRadius:  '9999px',
          fontSize:      '14px',
          fontWeight:    500,
          cursor:        'pointer',
          transition:    'background 0.35s ease',
          background:    scrolled ? C.brand : 'rgba(255,255,255,0.10)',
          color:         '#FFFFFF',
          border:        scrolled ? 'none' : '1px solid rgba(255,255,255,0.15)',
          fontFamily:    'inherit',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = scrolled ? C.brandHover : 'rgba(255,255,255,0.20)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = scrolled ? C.brand      : 'rgba(255,255,255,0.10)' }}
      >
        Get Started
      </button>
    </nav>
  )
}

// ─── Hero ────────────────────────────────────────────────────────────────────

function HeroSection() {
  const [contentVisible, setContentVisible] = useState(false)
  const router = useRouter()

  // Reveal supporting content after LUMIA finishes writing
  // Writing: delay 0.3s + duration 1.7s + 0.3s pause = 2.3s
  useEffect(() => {
    const t = setTimeout(() => setContentVisible(true), 2300)
    return () => clearTimeout(t)
  }, [])

  return (
    <section id="hero" style={{
      position:       'relative',
      minHeight:      '100vh',
      display:        'flex',
      flexDirection:  'column',
      alignItems:     'center',
      justifyContent: 'center',
      overflow:       'hidden',
    }}>
      {/* Background image */}
      <div style={{
        position:           'absolute',
        inset:              0,
        backgroundImage:    "url('/hero-bg.jpg')",
        backgroundSize:     'cover',
        backgroundPosition: 'center',
        backgroundRepeat:   'no-repeat',
        backgroundColor:    C.dark,
        zIndex:             0,
      }} />

      {/* Overlay — stronger so text is always legible */}
      <div style={{
        position:   'absolute',
        inset:      0,
        background: 'linear-gradient(180deg, rgba(8,20,20,0.62) 0%, rgba(8,20,20,0.52) 60%, rgba(8,20,20,0.68) 100%)',
        zIndex:     1,
      }} />

      {/* Content */}
      <div style={{
        position:      'relative',
        zIndex:        2,
        display:       'flex',
        flexDirection: 'column',
        alignItems:    'center',
        textAlign:     'center',
        padding:       '0 24px',
        maxWidth:      '900px',
      }}>

        {/* ── LUMIA writing animation (Apple "hello" style) ── */}
        <div style={{ position: 'relative', display: 'inline-block', marginBottom: '44px' }}>
          <motion.div
            initial={{ clipPath: 'inset(0 100% 0 0)' }}
            animate={{ clipPath: 'inset(0 0% 0 0)' }}
            transition={{ duration: 1.7, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
            style={{
              fontSize:      'clamp(6rem, 14vw, 12rem)',
              fontFamily:    'var(--font-instrument), Georgia, serif',
              fontStyle:     'italic',
              fontWeight:    400,
              color:         '#FFFFFF',
              letterSpacing: '-0.02em',
              lineHeight:    1,
              userSelect:    'none',
            }}
          >
            Lumia
          </motion.div>

          {/* Pen cursor that moves with the reveal */}
          <motion.div
            initial={{ left: '0%', opacity: 1 }}
            animate={{ left: '104%', opacity: 0 }}
            transition={{ duration: 1.7, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
            style={{
              position:     'absolute',
              top:          '6%',
              height:       '88%',
              width:        '2px',
              background:   'rgba(255,255,255,0.80)',
              borderRadius: '2px',
              boxShadow:    '0 0 10px rgba(255,255,255,0.55)',
            }}
          />
        </div>

        {/* Supporting content — fades in after writing completes */}
        <motion.div
          initial={{ opacity: 0, y: 22 }}
          animate={contentVisible ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.9, ease: EASE }}
          style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}
        >
          {/* Live pill */}
          <div style={{
            display:      'inline-flex',
            alignItems:   'center',
            gap:          '8px',
            background:   'rgba(255,255,255,0.08)',
            border:       '1px solid rgba(255,255,255,0.14)',
            borderRadius: '9999px',
            padding:      '6px 16px',
            marginBottom: '24px',
          }}>
            <motion.span
              animate={{ opacity: [1, 0.25, 1] }}
              transition={{ duration: 1.6, repeat: Infinity }}
              style={{ display: 'block', width: '7px', height: '7px', borderRadius: '50%', background: C.gold, flexShrink: 0 }}
            />
            <span style={{ fontSize: '13px', color: 'rgba(255,255,255,0.90)' }}>
              Live · 2,847 jobs mapped today
            </span>
          </div>

          {/* Tagline */}
          <h1 style={{
            fontSize:     'clamp(1.6rem, 3.2vw, 2.6rem)',
            fontFamily:   'var(--font-instrument), Georgia, serif',
            fontWeight:   400,
            color:        '#FFFFFF',
            lineHeight:   1.2,
            marginBottom: '16px',
          }}>
            Your career, mapped.
          </h1>

          {/* Subtext — higher contrast, text-shadow for legibility */}
          <p style={{
            fontSize:     '1.0625rem',
            color:        'rgba(255,255,255,0.84)',
            lineHeight:   1.7,
            maxWidth:     '460px',
            marginBottom: '36px',
            textShadow:   '0 1px 12px rgba(0,0,0,0.4)',
          }}>
            Lumia maps your resume against today&apos;s live job market and gives you a specific, weekly plan to get where you want to go.
          </p>

          {/* CTA row */}
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center' }}>
            <button
              onClick={() => router.push('/upload')}
              style={{
                padding:      '12px 30px',
                borderRadius: '9999px',
                fontSize:     '15px',
                fontWeight:   500,
                cursor:       'pointer',
                background:   C.brand,
                color:        '#FFFFFF',
                border:       'none',
                fontFamily:   'inherit',
                transition:   'background 0.25s ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = C.brandHover }}
              onMouseLeave={(e) => { e.currentTarget.style.background = C.brand }}
            >
              Get started free →
            </button>
            <button
              onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
              style={{
                padding:      '12px 30px',
                borderRadius: '9999px',
                fontSize:     '15px',
                fontWeight:   400,
                cursor:       'pointer',
                background:   'rgba(255,255,255,0.10)',
                color:        'rgba(255,255,255,0.88)',
                border:       '1px solid rgba(255,255,255,0.22)',
                fontFamily:   'inherit',
                transition:   'background 0.25s ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.18)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.10)' }}
            >
              See how it works
            </button>
          </div>
        </motion.div>
      </div>

      {/* Scroll indicator — visible after content loads */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={contentVisible ? { opacity: 1 } : {}}
        transition={{ duration: 0.7, delay: 0.4 }}
        style={{
          position:      'absolute',
          bottom:        '36px',
          left:          '50%',
          transform:     'translateX(-50%)',
          zIndex:        2,
          display:       'flex',
          flexDirection: 'column',
          alignItems:    'center',
          gap:           '6px',
          cursor:        'pointer',
        }}
        onClick={() => document.getElementById('problem')?.scrollIntoView({ behavior: 'smooth' })}
      >
        <span style={{
          fontSize:      '11px',
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color:         'rgba(255,255,255,0.68)',
          fontWeight:    500,
        }}>
          scroll to explore
        </span>
        <motion.div
          animate={{ y: [0, 7, 0] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        >
          <ChevronDown size={20} color="rgba(255,255,255,0.68)" />
        </motion.div>
      </motion.div>
    </section>
  )
}

// ─── Problem ─────────────────────────────────────────────────────────────────

function TabsIllustration({ inView }: { inView: boolean }) {
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    if (!inView) return
    const t = setTimeout(() => setCollapsed(true), 1800)
    return () => clearTimeout(t)
  }, [inView])

  const TABS = [
    C.brand, C.gold, C.textSecondary, C.brand, C.textSecondary,
    C.gold, C.brand, C.textSecondary, C.gold, C.brand,
    C.textSecondary, C.gold, C.brand, C.textSecondary, C.textSecondary,
  ]

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.92 }}
      animate={inView ? { opacity: 1, scale: 1 } : {}}
      transition={{ duration: 0.7, delay: 0.2 }}
      style={{
        background:   'rgba(255,255,255,0.04)',
        border:       '1px solid rgba(255,255,255,0.10)',
        borderRadius: '16px',
        padding:      '28px',
        aspectRatio:  '4/3',
        display:      'flex',
        flexDirection:'column',
        gap:          '12px',
      }}
    >
      {/* Browser chrome bar */}
      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
        {[0.15, 0.10, 0.07].map((op, i) => (
          <div key={i} style={{ width: '9px', height: '9px', borderRadius: '50%', background: `rgba(255,255,255,${op})` }} />
        ))}
        <div style={{ flex: 1, height: '22px', marginLeft: '10px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px' }} />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', flex: 1, alignContent: 'flex-start' }}>
        {TABS.map((color, i) => (
          <motion.div
            key={i}
            animate={collapsed
              ? { width: '100%', height: '3px', borderRadius: '2px' }
              : { width: '50px', height: '22px', borderRadius: '4px' }
            }
            transition={{ duration: 0.7, delay: i * 0.03, ease: EASE }}
            style={{
              background: `${color}${collapsed ? '88' : '33'}`,
              border:     `1px solid ${color}55`,
              flexShrink: 0,
            }}
          />
        ))}
      </div>

      {collapsed && (
        <motion.div
          initial={{ scaleX: 0, opacity: 0 }}
          animate={{ scaleX: 1, opacity: 1 }}
          transition={{ duration: 0.9, delay: 0.5 }}
          style={{
            height:          '2px',
            background:      `linear-gradient(90deg, ${C.brand}, ${C.gold})`,
            borderRadius:    '2px',
            transformOrigin: 'left',
          }}
        />
      )}

      <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.30)', fontFamily: 'monospace', textAlign: 'center' }}>
        {collapsed ? '1 clear signal' : '47 open tabs'}
      </div>
    </motion.div>
  )
}

function ProblemSection() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-100px' })

  return (
    <section id="problem" style={{
      background:  C.dark,
      minHeight:   '100vh',
      display:     'flex',
      alignItems:  'center',
      padding:     '80px clamp(24px, 7vw, 96px)',
    }}>
      <div style={{
        maxWidth:             '1200px',
        margin:               '0 auto',
        display:              'grid',
        gridTemplateColumns:  '1fr 1fr',
        gap:                  '80px',
        alignItems:           'center',
        width:                '100%',
      }}>
        <div ref={ref}>
          {/* Big headline */}
          <div style={{ marginBottom: '48px' }}>
            <div style={{
              fontSize:   'clamp(3rem, 6vw, 6rem)',
              fontFamily: 'var(--font-instrument), Georgia, serif',
              fontWeight: 400,
              lineHeight: 1.05,
              color:      '#FFFFFF',
            }}>
              Job searching
            </div>
            <div style={{
              fontSize:   'clamp(3rem, 6vw, 6rem)',
              fontFamily: 'var(--font-instrument), Georgia, serif',
              fontWeight: 400,
              fontStyle:  'italic',
              lineHeight: 1.05,
              color:      C.gold,
            }}>
              is broken.
            </div>
          </div>

          {/* Staggered bullet lines */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {PROBLEM_LINES.map((line, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={inView ? { opacity: 1, x: 0 } : {}}
                transition={{ duration: 0.6, delay: 0.3 + i * 0.2, ease: EASE }}
                style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}
              >
                <div style={{
                  width:    '40px',
                  height:   '1px',
                  background: C.gold,
                  marginTop: '12px',
                  flexShrink: 0,
                }} />
                <span style={{ fontSize: '18px', color: '#FFFFFF', fontWeight: 300, lineHeight: 1.6 }}>
                  {line}
                </span>
              </motion.div>
            ))}
          </div>
        </div>

        <TabsIllustration inView={inView} />
      </div>
    </section>
  )
}

// ─── How It Works ─────────────────────────────────────────────────────────────

function StepIllustration({ index, inView }: { index: number; inView: boolean }) {
  if (index === 0) {
    const tags = ['Python', 'React', 'SQL', 'AWS', 'TypeScript', 'FastAPI']
    return (
      <div style={{
        background:   `rgba(10,124,110,0.05)`,
        border:       `1px solid rgba(10,124,110,0.15)`,
        borderRadius: '16px',
        padding:      '32px',
        display:      'flex',
        flexWrap:     'wrap',
        gap:          '8px',
        alignContent: 'center',
        justifyContent: 'center',
        minHeight:    '180px',
      }}>
        {tags.map((tag, i) => (
          <motion.span
            key={tag}
            initial={{ opacity: 0, scale: 0.8, y: 8 }}
            animate={inView ? { opacity: 1, scale: 1, y: 0 } : {}}
            transition={{ duration: 0.45, delay: 0.3 + i * 0.1 }}
            style={{
              background:   i % 2 === 0 ? 'rgba(10,124,110,0.10)' : C.goldSubtle,
              color:        i % 2 === 0 ? C.brand               : C.gold,
              border:       `1px solid ${i % 2 === 0 ? 'rgba(10,124,110,0.25)' : 'rgba(201,135,58,0.25)'}`,
              borderRadius: '9999px',
              padding:      '6px 14px',
              fontSize:     '13px',
              fontWeight:   500,
            }}
          >
            {tag}
          </motion.span>
        ))}
      </div>
    )
  }

  if (index === 1) {
    const clusters: [number, number][] = [[60, 45], [200, 40], [40, 140], [220, 145], [130, 28]]
    return (
      <div style={{
        background:   'rgba(10,124,110,0.05)',
        border:       '1px solid rgba(10,124,110,0.15)',
        borderRadius: '16px',
        display:      'flex',
        alignItems:   'center',
        justifyContent: 'center',
        minHeight:    '180px',
        overflow:     'hidden',
      }}>
        <svg width="280" height="180" viewBox="0 0 280 180">
          {clusters.map(([cx, cy], i) => (
            <g key={i}>
              <motion.line
                x1={130} y1={95} x2={cx} y2={cy}
                stroke={C.brand} strokeWidth="1" strokeOpacity="0.35"
                initial={{ pathLength: 0 }}
                animate={inView ? { pathLength: 1 } : {}}
                transition={{ duration: 0.6, delay: 0.4 + i * 0.1 }}
              />
              <motion.circle
                cx={cx} cy={cy} r="14"
                fill={C.brand} fillOpacity="0.12"
                stroke={C.brand} strokeWidth="1" strokeOpacity="0.45"
                initial={{ scale: 0 }}
                animate={inView ? { scale: 1 } : {}}
                transition={{ duration: 0.4, delay: 0.5 + i * 0.1 }}
              />
            </g>
          ))}
          <motion.circle
            cx={130} cy={95} r="24"
            fill={C.gold} fillOpacity="0.18"
            stroke={C.gold} strokeWidth="2"
            initial={{ scale: 0 }}
            animate={inView ? { scale: 1 } : {}}
            transition={{ duration: 0.5, delay: 0.3, type: 'spring', stiffness: 200 }}
          />
          <motion.circle
            cx={130} cy={95} r="9"
            fill={C.gold}
            initial={{ scale: 0 }}
            animate={inView ? { scale: 1 } : {}}
            transition={{ duration: 0.4, delay: 0.4 }}
          />
          <text x={130} y={126} textAnchor="middle" fontSize="10" fill={C.textSecondary} fontFamily="monospace">
            you
          </text>
        </svg>
      </div>
    )
  }

  // Step 3 — plan
  const items = [
    { week: 'Week 1', tasks: ['Build portfolio project', 'Learn TypeScript patterns'] },
    { week: 'Week 2', tasks: ['System design practice', 'Apply to 3 target roles'] },
  ]
  return (
    <div style={{
      background:   'rgba(10,124,110,0.05)',
      border:       '1px solid rgba(10,124,110,0.15)',
      borderRadius: '16px',
      padding:      '24px',
      minHeight:    '180px',
    }}>
      {items.map((item, wi) => (
        <div key={wi} style={{ marginBottom: wi < items.length - 1 ? '20px' : 0 }}>
          <div style={{
            fontSize:      '10px',
            fontWeight:    600,
            letterSpacing: '0.08em',
            color:         C.brand,
            textTransform: 'uppercase',
            marginBottom:  '10px',
          }}>
            {item.week}
          </div>
          {item.tasks.map((task, ti) => (
            <motion.div
              key={ti}
              initial={{ opacity: 0, x: 10 }}
              animate={inView ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.45, delay: 0.4 + wi * 0.25 + ti * 0.12 }}
              style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={inView ? { scale: 1 } : {}}
                transition={{ duration: 0.3, delay: 0.55 + wi * 0.25 + ti * 0.12 }}
                style={{
                  width:        '16px',
                  height:       '16px',
                  borderRadius: '4px',
                  background:   C.goldSubtle,
                  border:       `1px solid rgba(201,135,58,0.35)`,
                  display:      'flex',
                  alignItems:   'center',
                  justifyContent: 'center',
                  flexShrink:   0,
                }}
              >
                <span style={{ fontSize: '10px', color: C.gold }}>✓</span>
              </motion.div>
              <span style={{ fontSize: '13px', color: C.textSecondary }}>{task}</span>
            </motion.div>
          ))}
        </div>
      ))}
    </div>
  )
}

function StepRow({ step, index }: { step: typeof HOW_STEPS[0]; index: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, x: -24 }}
      animate={inView ? { opacity: 1, x: 0 } : {}}
      transition={{ duration: 0.7, ease: EASE }}
      style={{
        display:             'grid',
        gridTemplateColumns: '1fr 1fr',
        gap:                 '60px',
        padding:             '60px 0 60px 44px',
        borderBottom:        index < HOW_STEPS.length - 1
          ? '1px solid rgba(13,31,31,0.08)' : 'none',
        position: 'relative',
      }}
    >
      {/* Gold dot on the timeline */}
      <div style={{
        position:     'absolute',
        left:         '-5px',
        top:          '74px',
        width:        '12px',
        height:       '12px',
        borderRadius: '50%',
        background:   C.gold,
        border:       `2px solid ${C.base}`,
      }} />

      <div style={{ position: 'relative' }}>
        {/* Ghost number */}
        <span style={{
          position:     'absolute',
          top:          '-20px',
          left:         '-10px',
          fontSize:     '160px',
          fontFamily:   'var(--font-instrument), Georgia, serif',
          fontWeight:   700,
          lineHeight:   1,
          color:        'rgba(13,31,31,0.035)',
          userSelect:   'none',
          letterSpacing:'-0.04em',
          pointerEvents:'none',
        }}>
          {step.num}
        </span>
        <h3 style={{
          fontSize:   '2.5rem',
          fontFamily: 'var(--font-instrument), Georgia, serif',
          fontWeight: 400,
          color:      C.textPrimary,
          lineHeight: 1.15,
          marginBottom: '16px',
          position:   'relative',
        }}>
          {step.title}
        </h3>
        <p style={{
          fontSize:   '1.125rem',
          color:      C.textSecondary,
          lineHeight: 1.75,
          maxWidth:   '400px',
        }}>
          {step.body}
        </p>
      </div>

      <StepIllustration index={index} inView={inView} />
    </motion.div>
  )
}

function HowItWorksSection() {
  return (
    <section id="how-it-works" style={{ background: C.base, padding: '120px clamp(24px, 7vw, 96px)' }}>
      <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
        <div style={{ marginBottom: '80px' }}>
          <p style={{
            fontSize:      '11px',
            fontWeight:    600,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color:         C.brand,
            marginBottom:  '16px',
          }}>
            THE PROCESS
          </p>
          <h2 style={{
            fontSize:   'clamp(2.5rem, 4vw, 4rem)',
            fontFamily: 'var(--font-instrument), Georgia, serif',
            fontWeight: 400,
            color:      C.textPrimary,
            lineHeight: 1.1,
          }}>
            Three steps to clarity.
          </h2>
        </div>

        <div style={{ position: 'relative' }}>
          {/* Vertical timeline line */}
          <div style={{
            position:   'absolute',
            left:       0,
            top:        0,
            bottom:     0,
            width:      '2px',
            background: `linear-gradient(to bottom, ${C.brand}, ${C.gold})`,
          }} />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {HOW_STEPS.map((step, i) => (
              <StepRow key={i} step={step} index={i} />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── Market Signal ────────────────────────────────────────────────────────────

function Counter({ to, suffix = '' }: { to: number; suffix?: string }) {
  const ref    = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true })

  useEffect(() => {
    if (!inView || !ref.current) return
    let start: number | null = null
    const duration = 1500
    let raf: number

    function tick(ts: number) {
      if (!start) start = ts
      const t = Math.min((ts - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3)
      if (ref.current) ref.current.textContent = Math.round(eased * to).toLocaleString() + suffix
      if (t < 1) raf = requestAnimationFrame(tick)
    }

    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [inView, to, suffix])

  return <span ref={ref}>0{suffix}</span>
}

function MarketSignalSection() {
  const barsRef    = useRef<HTMLDivElement>(null)
  const barsInView = useInView(barsRef, { once: true })

  return (
    <section id="market-signal" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', minHeight: '100vh' }}>
      {/* Left — dark */}
      <div style={{
        background:    C.dark,
        padding:       '80px clamp(24px, 5vw, 72px)',
        display:       'flex',
        flexDirection: 'column',
        justifyContent:'center',
      }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '48px' }}>
          <motion.span
            animate={{ opacity: [1, 0.25, 1] }}
            transition={{ duration: 1.6, repeat: Infinity }}
            style={{ display: 'block', width: '8px', height: '8px', borderRadius: '50%', background: C.gold }}
          />
          <span style={{ fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.45)', fontWeight: 600 }}>
            LIVE TODAY
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '40px', marginBottom: '56px' }}>
          {[
            { to: 2847, suffix: '',   label: 'jobs ingested in the last 24 hours',          color: '#FFFFFF' },
            { to: 14,   suffix: '',   label: 'role clusters mapped across all industries',   color: '#FFFFFF' },
            { to: 89,   suffix: '%',  label: 'average match accuracy',                       color: C.gold   },
          ].map((item, i) => (
            <div key={i}>
              <div style={{
                fontSize:   'clamp(2.5rem, 4vw, 4.5rem)',
                fontFamily: 'var(--font-instrument), Georgia, serif',
                fontWeight: 400,
                color:      item.color,
                lineHeight: 1,
                marginBottom: '6px',
              }}>
                <Counter to={item.to} suffix={item.suffix} />
              </div>
              <div style={{ fontSize: '14px', color: 'rgba(255,255,255,0.45)', lineHeight: 1.5 }}>
                {item.label}
              </div>
            </div>
          ))}
        </div>

        {/* Ticker */}
        <div style={{ overflow: 'hidden' }}>
          <div className="animate-ticker" style={{ display: 'flex', width: 'max-content' }}>
            {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
              <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: '12px', padding: '0 18px' }}>
                <span style={{ fontSize: '12px', fontFamily: 'monospace', color: 'rgba(255,255,255,0.30)', whiteSpace: 'nowrap' }}>
                  {item}
                </span>
                <span style={{ color: C.gold, fontSize: '8px' }}>·</span>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Right — light */}
      <div style={{
        background:    C.base,
        padding:       '80px clamp(24px, 5vw, 72px)',
        display:       'flex',
        flexDirection: 'column',
        justifyContent:'center',
      }}>
        <h2 style={{
          fontSize:   'clamp(2rem, 3vw, 3rem)',
          fontFamily: 'var(--font-instrument), Georgia, serif',
          fontWeight: 400,
          color:      C.textPrimary,
          lineHeight: 1.15,
          marginBottom:'20px',
        }}>
          The market, live.
        </h2>
        <p style={{
          fontSize:    '1rem',
          color:       C.textSecondary,
          lineHeight:  1.75,
          maxWidth:    '400px',
          marginBottom:'48px',
        }}>
          Lumia ingests fresh job postings every 24 hours across every industry. Not last week&apos;s data.
          Not a keyword match. Today&apos;s actual market signal.
        </p>

        {/* Domain bars */}
        <div ref={barsRef} style={{ display: 'flex', flexDirection: 'column', gap: '14px', maxWidth: '380px' }}>
          {DOMAIN_BARS.map((d, i) => (
            <div key={d.label}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                <span style={{ fontSize: '13px', color: C.textSecondary }}>{d.label}</span>
                <span style={{ fontSize: '13px', color: i === 0 ? C.brand : C.textSecondary, fontWeight: i === 0 ? 600 : 400 }}>
                  {d.pct}%
                </span>
              </div>
              <div style={{
                height:       '6px',
                background:   'rgba(13,31,31,0.06)',
                borderRadius: '9999px',
                overflow:     'hidden',
              }}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={barsInView ? { width: `${(d.pct / 23) * 100}%` } : {}}
                  transition={{ duration: 0.85, delay: 0.1 + i * 0.12, ease: EASE }}
                  style={{
                    height:       '100%',
                    background:   i === 0 ? C.brand : 'rgba(10,124,110,0.38)',
                    borderRadius: '9999px',
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── Product Flow ─────────────────────────────────────────────────────────────

function ProductFlowSection() {
  const ref = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] })

  const y1 = useTransform(scrollYProgress, [0, 1], [60,  -60])
  const y2 = useTransform(scrollYProgress, [0, 1], [30,  -30])
  const y3 = useTransform(scrollYProgress, [0, 1], [0,   -10])

  return (
    <section id="product-flow" ref={ref} style={{ background: C.base, padding: '140px clamp(24px, 7vw, 96px)', overflow: 'hidden' }}>
      <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
        <h2 style={{
          fontSize:     'clamp(2rem, 4vw, 3.5rem)',
          fontFamily:   'var(--font-instrument), Georgia, serif',
          fontWeight:   400,
          color:        C.textPrimary,
          textAlign:    'center',
          marginBottom: '80px',
          lineHeight:   1.15,
        }}>
          What happens after you upload.
        </h2>

        {/* Stacked panels with parallax */}
        <div style={{ position: 'relative', height: '420px', maxWidth: '720px', margin: '0 auto 48px' }}>
          {/* Panel 1 — back, blurred */}
          <motion.div style={{ y: y1, position: 'absolute', inset: 0, zIndex: 1 }}>
            <div style={{
              background:   C.surface,
              border:       `1px solid rgba(10,124,110,0.12)`,
              borderRadius: '20px',
              padding:      '32px',
              height:       '100%',
              opacity:      0.55,
              filter:       'blur(1.5px)',
            }}>
              <div style={{ fontSize: '12px', color: C.textSecondary, marginBottom: '16px' }}>Resume Upload</div>
              <div style={{
                border:         `2px dashed rgba(10,124,110,0.22)`,
                borderRadius:   '12px',
                height:         '75%',
                display:        'flex',
                alignItems:     'center',
                justifyContent: 'center',
                color:          C.brand,
                fontSize:       '14px',
              }}>
                Drop your resume here
              </div>
            </div>
          </motion.div>

          {/* Panel 2 — middle */}
          <motion.div style={{ y: y2, position: 'absolute', inset: '22px 22px 0', zIndex: 2 }}>
            <div style={{
              background:   C.surface,
              border:       `1px solid rgba(10,124,110,0.20)`,
              borderRadius: '20px',
              padding:      '32px',
              height:       '100%',
              opacity:      0.82,
            }}>
              <div style={{ fontSize: '12px', color: C.textSecondary, marginBottom: '16px' }}>Career Cluster Map</div>
              <svg width="100%" height="78%" viewBox="0 0 420 200">
                {([[80,55],[340,55],[60,155],[360,155]] as [number,number][]).map(([cx,cy], i) => (
                  <g key={i}>
                    <line x1={210} y1={100} x2={cx} y2={cy} stroke={C.brand} strokeWidth="1" strokeOpacity="0.28" />
                    <circle cx={cx} cy={cy} r="19" fill="rgba(10,124,110,0.08)" stroke={C.brand} strokeWidth="1" strokeOpacity="0.35" />
                  </g>
                ))}
                <circle cx={210} cy={100} r="28" fill={C.goldSubtle} stroke={C.gold} strokeWidth="2" />
                <circle cx={210} cy={100} r="11" fill={C.gold} />
              </svg>
            </div>
          </motion.div>

          {/* Panel 3 — front, sharp */}
          <motion.div style={{ y: y3, position: 'absolute', inset: '44px 44px 0', zIndex: 3 }}>
            <div style={{
              background:   C.surface,
              boxShadow:    '0 20px 60px rgba(13,31,31,0.11)',
              borderRadius: '20px',
              padding:      '32px',
              height:       '100%',
            }}>
              <div style={{
                fontSize:      '11px',
                fontWeight:    600,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color:         C.brand,
                marginBottom:  '20px',
              }}>
                Your Execution Plan
              </div>
              {[
                { t: 'Learn TypeScript patterns',  done: true  },
                { t: 'Build portfolio project',    done: true  },
                { t: 'System design practice',     done: false },
                { t: 'Apply to 3 ML roles',        done: false },
              ].map((item, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                  <div style={{
                    width:        '16px',
                    height:       '16px',
                    borderRadius: '4px',
                    background:   item.done ? C.goldSubtle : 'rgba(13,31,31,0.05)',
                    border:       `1px solid ${item.done ? 'rgba(201,135,58,0.35)' : 'rgba(13,31,31,0.12)'}`,
                    display:      'flex',
                    alignItems:   'center',
                    justifyContent: 'center',
                    flexShrink:   0,
                  }}>
                    {item.done && <span style={{ fontSize: '10px', color: C.gold }}>✓</span>}
                  </div>
                  <span style={{
                    fontSize:       '13px',
                    color:          item.done ? C.textSecondary : C.textPrimary,
                    textDecoration: item.done ? 'line-through'  : 'none',
                  }}>
                    {item.t}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        <p style={{ textAlign: 'center', fontSize: '14px', color: C.textSecondary, lineHeight: 1.6 }}>
          Built for engineers, analysts, researchers, and everyone in between.
        </p>
      </div>
    </section>
  )
}

// ─── Final CTA ────────────────────────────────────────────────────────────────

function CtaSection() {
  const router = useRouter()

  return (
    <section id="cta" style={{
      background:    C.dark,
      minHeight:     '100vh',
      display:       'flex',
      flexDirection: 'column',
      alignItems:    'center',
      justifyContent:'center',
      textAlign:     'center',
      padding:       '80px 24px',
      position:      'relative',
      overflow:      'hidden',
    }}>
      {/* Radial glow */}
      <div style={{
        position:        'absolute',
        top:             '50%',
        left:            '50%',
        transform:       'translate(-50%, -50%)',
        width:           '640px',
        height:          '640px',
        borderRadius:    '50%',
        background:      'radial-gradient(circle, rgba(10,124,110,0.14) 0%, transparent 70%)',
        pointerEvents:   'none',
      }} />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.8, ease: EASE }}
        style={{ position: 'relative', zIndex: 1 }}
      >
        <h2 style={{
          fontSize:     'clamp(2.5rem, 5vw, 4.5rem)',
          fontFamily:   'var(--font-instrument), Georgia, serif',
          fontWeight:   400,
          color:        '#FFFFFF',
          marginBottom: '20px',
          lineHeight:   1.12,
        }}>
          You&apos;re closer than you think.
        </h2>

        <p style={{
          fontSize:     '1.125rem',
          color:        'rgba(255,255,255,0.48)',
          lineHeight:   1.75,
          maxWidth:     '480px',
          margin:       '0 auto 44px',
        }}>
          Upload your resume. See where you stand today.<br />
          Get a plan you can actually execute this week.
        </p>

        <button
          onClick={() => router.push('/upload')}
          style={{
            background:   C.gold,
            color:        C.dark,
            border:       'none',
            borderRadius: '8px',
            padding:      '18px 48px',
            fontSize:     '16px',
            fontWeight:   500,
            cursor:       'pointer',
            transition:   'transform 0.22s ease, filter 0.22s ease',
            letterSpacing:'-0.01em',
            display:      'block',
            margin:       '0 auto 16px',
            fontFamily:   'inherit',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'scale(1.03)'
            e.currentTarget.style.filter    = 'brightness(1.08)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'scale(1)'
            e.currentTarget.style.filter    = 'brightness(1)'
          }}
        >
          Upload your resume →
        </button>

        <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.28)' }}>
          No account required · Takes 2 minutes
        </p>
      </motion.div>

      {/* Watermark wordmark */}
      <div style={{
        position:  'absolute',
        bottom:    '48px',
        left:      '50%',
        transform: 'translateX(-50%)',
        display:   'flex',
        gap:       '2px',
      }}>
        {'LUMIA'.split('').map((l, i) => (
          <span key={i} style={{
            fontSize:      '28px',
            fontWeight:    700,
            letterSpacing: '0.08em',
            color:         'rgba(255,255,255,0.10)',
          }}>
            {l}
          </span>
        ))}
      </div>
    </section>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div style={{ background: C.base }}>
      <Navbar />
      <HeroSection />
      <ProblemSection />
      <HowItWorksSection />
      <MarketSignalSection />
      <ProductFlowSection />
      <CtaSection />
    </div>
  )
}
