'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  motion, useInView, useScroll, useTransform,
} from 'framer-motion'
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

// ─── Lumia SVG script animation ──────────────────────────────────────────────

function LumiaScript() {
  const [fontReady, setFontReady] = useState(false)

  useEffect(() => {
    document.fonts.ready.then(() => setFontReady(true))
  }, [])

  return (
    <svg
      viewBox="0 0 900 240"
      style={{ display: 'block', margin: '0 auto', height: '15vw', width: 'auto', maxWidth: '70vw', overflow: 'visible' }}
    >
      <motion.text
        x="450"
        y="200"
        textAnchor="middle"
        fontFamily="var(--font-dancing), cursive"
        fontSize={200}
        fill="none"
        stroke="rgba(255,255,255,0.94)"
        strokeWidth={5}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={8000}
        initial={{ strokeDashoffset: 8000, opacity: 0 }}
        animate={fontReady ? { strokeDashoffset: 0, opacity: 1 } : {}}
        transition={{
          strokeDashoffset: { duration: 33, ease: 'linear' },
          opacity: { duration: 0.1 },
        }}
      >
        Lumia
      </motion.text>
    </svg>
  )
}

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
      transition:     'background 0.4s ease',
      background:     scrolled ? 'rgba(8,20,20,0.90)' : 'rgba(8,20,20,0.60)',
      backdropFilter: 'blur(28px)',
      WebkitBackdropFilter: 'blur(28px)',
      borderBottom:   '1px solid rgba(255,255,255,0.14)',
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
              fontSize:      '19px',
              fontWeight:    700,
              letterSpacing: '0.06em',
              color:         '#FFFFFF',
            }}
          >
            {l}
          </motion.span>
        ))}
      </div>

      {/* Right side: links + CTA */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <div style={{ display: 'flex', gap: '10px' }}>
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
                background:           'rgba(255,255,255,0.10)',
                border:               '1px solid rgba(255,255,255,0.22)',
                borderRadius:         '9999px',
                fontSize:             '14px',
                fontWeight:           500,
                cursor:               'pointer',
                color:                '#FFFFFF',
                transition:           'background 0.18s ease, border-color 0.18s ease',
                fontFamily:           'inherit',
                padding:              '6px 18px',
                backdropFilter:       'blur(12px)',
                WebkitBackdropFilter: 'blur(12px)',
              }}
              onMouseEnter={(e) => {
                const el = e.currentTarget
                el.style.background  = 'rgba(255,255,255,0.22)'
                el.style.borderColor = 'rgba(255,255,255,0.40)'
              }}
              onMouseLeave={(e) => {
                const el = e.currentTarget
                el.style.background  = 'rgba(255,255,255,0.10)'
                el.style.borderColor = 'rgba(255,255,255,0.22)'
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <button
          onClick={() => router.push('/upload')}
          style={{
            padding:       '9px 22px',
            borderRadius:  '9999px',
            fontSize:      '14px',
            fontWeight:    500,
            cursor:        'pointer',
            transition:    'background 0.35s ease',
            background:    C.brand,
            color:         '#FFFFFF',
            border:        'none',
            fontFamily:    'inherit',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = C.brandHover }}
          onMouseLeave={(e) => { e.currentTarget.style.background = C.brand }}
        >
          Get Started
        </button>
      </div>
    </nav>
  )
}

// ─── Hero ────────────────────────────────────────────────────────────────────

function HeroSection() {
  const [showContent, setShowContent] = useState(false)
  const router = useRouter()

  useEffect(() => {
    const t = setTimeout(() => setShowContent(true), 2000)
    return () => clearTimeout(t)
  }, [])

  return (
    <section
      id="hero"
      style={{ position: 'relative', height: '100vh', overflow: 'hidden' }}
    >
      {/* ── Background video ── */}
      <video
        autoPlay
        muted
        loop
        playsInline
        style={{
          position:   'absolute',
          inset:      0,
          width:      '100%',
          height:     '100%',
          objectFit:  'cover',
          zIndex:     0,
        }}
      >
        <source src="/hero-bg.mp4" type="video/mp4" />
      </video>

      {/* Static gradient */}
      <div style={{
        position:   'absolute', inset: 0, zIndex: 1,
        background: 'linear-gradient(105deg, rgba(8,20,20,0.35) 0%, rgba(8,20,20,0.12) 38%, rgba(8,20,20,0.12) 54%, rgba(8,20,20,0.86) 100%)',
      }} />

      {/* Warm ambient */}
      <div style={{
        position:   'absolute', inset: 0, zIndex: 1, pointerEvents: 'none',
        background: 'radial-gradient(ellipse 60% 55% at 35% 60%, rgba(201,135,58,0.06) 0%, transparent 70%)',
      }} />

      {/* ── LUMIA SVG script ── */}
      <div style={{
        position:  'absolute',
        top:       '30%',
        left:      0,
        right:     0,
        transform: 'translateY(-50%)',
        zIndex:    2,
        textAlign: 'center',
      }}>
        <LumiaScript />
      </div>

      {/* ── RIGHT PANEL ── */}
      <motion.div
        style={{
          position:             'absolute',
          right:                'clamp(28px, 6vw, 88px)',
          top:                  '64%',
          transform:            'translateY(-50%)',
          zIndex:               3,
          width:                'clamp(280px, 36%, 460px)',
          display:              'flex',
          flexDirection:        'column',
          alignItems:           'flex-start',
          background:           'rgba(8,20,20,0.55)',
          backdropFilter:       'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          borderRadius:         '20px',
          border:               '1px solid rgba(255,255,255,0.10)',
          padding:              '28px 32px',
        }}
        initial={{ opacity: 0 }}
        animate={showContent ? { opacity: 1 } : { opacity: 0 }}
        transition={{ duration: 0.9, delay: 0.6, ease: 'easeOut' }}
      >
        {/* Live pill */}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: '8px',
          background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.14)',
          borderRadius: '9999px', padding: '6px 16px', marginBottom: '18px',
        }}>
          <motion.span
            animate={{ opacity: [1, 0.25, 1] }}
            transition={{ duration: 1.6, repeat: Infinity }}
            style={{ display: 'block', width: '7px', height: '7px', borderRadius: '50%', background: C.gold, flexShrink: 0 }}
          />
          <span style={{ fontSize: '13px', color: 'rgba(255,255,255,0.90)' }}>
            Live · 9,000+ jobs mapped today
          </span>
        </div>

        <h1 style={{
          fontSize:     'clamp(1.4rem, 2.4vw, 2.2rem)',
          fontWeight:   600,
          color:        '#FFFFFF',
          lineHeight:   1.22,
          marginBottom: '14px',
          textShadow:   '0 2px 16px rgba(0,0,0,0.6)',
        }}>
          47 open tabs. Zero replies. There&apos;s a better way.
        </h1>

        <p style={{
          fontSize:     '1rem',
          color:        'rgba(255,255,255,0.92)',
          lineHeight:   1.75,
          marginBottom: '28px',
        }}>
          Lumia maps your resume against today&apos;s live job market and gives you a specific, weekly plan to get where you want to go.
        </p>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            onClick={() => router.push('/upload')}
            style={{
              padding: '11px 26px', borderRadius: '9999px', fontSize: '14px', fontWeight: 500,
              cursor: 'pointer', background: C.brand, color: '#FFFFFF', border: 'none',
              fontFamily: 'inherit', transition: 'background 0.25s ease',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = C.brandHover }}
            onMouseLeave={(e) => { e.currentTarget.style.background = C.brand }}
          >
            Get started free →
          </button>
          <button
            onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
            style={{
              padding: '11px 26px', borderRadius: '9999px', fontSize: '14px', fontWeight: 500,
              cursor: 'pointer', background: 'rgba(255,255,255,0.18)', color: '#FFFFFF',
              border: '1px solid rgba(255,255,255,0.45)', fontFamily: 'inherit', transition: 'background 0.25s ease',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.30)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.18)' }}
          >
            See how it works
          </button>
        </div>
      </motion.div>

      {/* ── Scroll indicator ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={showContent ? { opacity: 1 } : { opacity: 0 }}
        transition={{ duration: 0.9, delay: 0.6 }}
        onClick={() => document.getElementById('problem')?.scrollIntoView({ behavior: 'smooth' })}
        style={{
          position:      'absolute',
          bottom:        '32px',
          left:          '50%',
          transform:     'translateX(-50%)',
          zIndex:        5,
          display:       'flex',
          flexDirection: 'column',
          alignItems:    'center',
          gap:           '6px',
          cursor:        'pointer',
        }}
      >
        <span style={{
          fontSize: '11px', letterSpacing: '0.13em', textTransform: 'uppercase',
          color: '#FFFFFF', fontWeight: 600, whiteSpace: 'nowrap',
          textShadow: '0 1px 8px rgba(0,0,0,0.8)',
        }}>
          See where you stand
        </span>
        <motion.div
          animate={{ y: [0, 6, 0] }}
          transition={{ duration: 1.9, repeat: Infinity, ease: 'easeInOut' }}
        >
          <ChevronDown size={17} color="#FFFFFF" />
        </motion.div>
      </motion.div>
    </section>
  )
}

// ─── Problem ─────────────────────────────────────────────────────────────────

function TabsIllustration({ inView }: { inView: boolean }) {
  const [collapsed, setCollapsed] = useState(false)
  const active = useRef(false)

  useEffect(() => {
    if (!inView) return
    active.current = true

    function runCycle() {
      if (!active.current) return
      setCollapsed(false)
      setTimeout(() => {
        if (!active.current) return
        setCollapsed(true)
        setTimeout(() => { if (active.current) runCycle() }, 2600)
      }, 2400)
    }

    runCycle()
    return () => { active.current = false }
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
        background:    'linear-gradient(145deg, #FFFFFF 0%, rgba(245,246,244,0.8) 100%)',
        border:        '1px solid rgba(13,31,31,0.10)',
        borderRadius:  '20px',
        padding:       '28px',
        aspectRatio:   '4/3',
        display:       'flex',
        flexDirection: 'column',
        gap:           '12px',
        boxShadow:     '0 8px 40px rgba(13,31,31,0.10), 0 2px 8px rgba(13,31,31,0.05)',
        position:      'relative',
        overflow:      'hidden',
      }}
    >
      {/* Subtle bottom glow that transitions */}
      <div style={{
        position:      'absolute',
        bottom:        0,
        left:          0,
        right:         0,
        height:        '45%',
        background:    collapsed
          ? 'linear-gradient(to top, rgba(10,124,110,0.08), transparent)'
          : 'linear-gradient(to top, rgba(201,135,58,0.06), transparent)',
        pointerEvents: 'none',
        transition:    'background 1s ease',
      }} />

      {/* Browser chrome */}
      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', position: 'relative' }}>
        {[0.55, 0.35, 0.20].map((op, i) => (
          <div key={i} style={{ width: '9px', height: '9px', borderRadius: '50%', background: `rgba(13,31,31,${op})` }} />
        ))}
        <div style={{ flex: 1, height: '22px', marginLeft: '10px', background: 'rgba(13,31,31,0.05)', borderRadius: '4px' }} />
        <div style={{
          fontSize:   '10px',
          fontWeight: 600,
          color:      collapsed ? C.brand : C.gold,
          background: collapsed ? 'rgba(10,124,110,0.10)' : 'rgba(201,135,58,0.12)',
          border:     `1px solid ${collapsed ? 'rgba(10,124,110,0.25)' : 'rgba(201,135,58,0.25)'}`,
          borderRadius: '9999px',
          padding:    '2px 9px',
          transition: 'all 0.6s ease',
          whiteSpace: 'nowrap',
          flexShrink: 0,
        }}>
          {collapsed ? '1 signal' : '47 tabs'}
        </div>
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
            height:          '3px',
            background:      `linear-gradient(90deg, ${C.brand}, ${C.gold}, ${C.brand})`,
            borderRadius:    '2px',
            transformOrigin: 'left',
          }}
        />
      )}

      <div style={{
        fontSize:   '12px',
        color:      collapsed ? C.brand : 'rgba(13,31,31,0.45)',
        fontFamily: 'monospace',
        textAlign:  'center',
        fontWeight: collapsed ? 600 : 400,
        transition: 'color 0.5s ease',
      }}>
        {collapsed ? '✓ 1 clear signal' : '47 open tabs, 0 clarity'}
      </div>
    </motion.div>
  )
}

function ProblemSection() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: false, margin: '-100px' })

  return (
    <section id="problem" style={{
      background:  C.base,
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
          <div style={{ marginBottom: '48px' }}>
            <div style={{
              fontSize:   'clamp(3rem, 6vw, 6rem)',
              fontFamily: 'inherit',
              fontWeight: 400,
              lineHeight: 1.05,
              color:      C.textPrimary,
            }}>
              Job searching
            </div>
            <div style={{
              fontSize:   'clamp(3rem, 6vw, 6rem)',
              fontFamily: 'inherit',
              fontWeight: 700,
              lineHeight: 1.05,
              color:      C.gold,
            }}>
              is broken.
            </div>
          </div>

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
                <span style={{ fontSize: '18px', color: C.textPrimary, fontWeight: 400, lineHeight: 1.6 }}>
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

function StepCard({ step, index }: { step: typeof HOW_STEPS[0]; index: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })
  const accents = [C.brand, C.gold, C.textSecondary] as const
  const accent = accents[index % accents.length]

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 50 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.75, delay: index * 0.15, ease: EASE }}
      whileHover={{ y: -10, boxShadow: '0 28px 64px rgba(13,31,31,0.14)' }}
      style={{
        background:    C.surface,
        border:        '1px solid rgba(13,31,31,0.07)',
        borderRadius:  '24px',
        padding:       '40px 32px 36px',
        position:      'relative',
        overflow:      'hidden',
        boxShadow:     '0 4px 24px rgba(13,31,31,0.06)',
        display:       'flex',
        flexDirection: 'column',
        gap:           '24px',
        transition:    'box-shadow 0.3s ease',
      }}
    >
      {/* Top accent sweep */}
      <motion.div
        initial={{ scaleX: 0 }}
        animate={inView ? { scaleX: 1 } : {}}
        transition={{ duration: 0.7, delay: index * 0.15 + 0.3 }}
        style={{
          height:          '3px',
          background:      `linear-gradient(90deg, ${accent}, transparent)`,
          borderRadius:    '2px',
          transformOrigin: 'left',
          position:        'absolute',
          top:             0,
          left:            0,
          right:           0,
        }}
      />

      {/* Ghost number */}
      <span style={{
        position:      'absolute',
        right:         '-8px',
        top:           '-16px',
        fontSize:      '140px',
        fontWeight:    700,
        lineHeight:    1,
        color:         'rgba(13,31,31,0.025)',
        userSelect:    'none',
        letterSpacing: '-0.04em',
        pointerEvents: 'none',
      }}>
        {step.num}
      </span>

      {/* Step chip */}
      <div style={{
        display:      'inline-flex',
        alignItems:   'center',
        gap:          '7px',
        background:   `${accent}18`,
        border:       `1px solid ${accent}35`,
        borderRadius: '9999px',
        padding:      '5px 14px',
        width:        'fit-content',
      }}>
        <motion.span
          animate={{ scale: [1, 1.4, 1] }}
          transition={{ duration: 2, repeat: Infinity, delay: index * 0.6 }}
          style={{ width: '6px', height: '6px', borderRadius: '50%', background: accent, display: 'block', flexShrink: 0 }}
        />
        <span style={{ fontSize: '11px', fontWeight: 700, color: accent, letterSpacing: '0.08em' }}>
          STEP {step.num}
        </span>
      </div>

      {/* Text */}
      <div>
        <h3 style={{ fontSize: '1.55rem', fontWeight: 400, color: C.textPrimary, lineHeight: 1.2, marginBottom: '10px', fontFamily: 'inherit' }}>
          {step.title}
        </h3>
        <p style={{ fontSize: '0.95rem', color: C.textSecondary, lineHeight: 1.75 }}>
          {step.body}
        </p>
      </div>

      {/* Illustration */}
      <StepIllustration index={index} inView={inView} />
    </motion.div>
  )
}

function HowItWorksSection() {
  return (
    <section id="how-it-works" style={{ background: C.surface, padding: '120px clamp(24px, 7vw, 96px)' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7, ease: EASE }}
          style={{ marginBottom: '72px', textAlign: 'center' }}
        >
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
            fontFamily: 'inherit',
            fontWeight: 400,
            color:      C.textPrimary,
            lineHeight: 1.1,
          }}>
            Three steps to clarity.
          </h2>
        </motion.div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
          {HOW_STEPS.map((step, i) => (
            <StepCard key={i} step={step} index={i} />
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── Knowledge Graph ─────────────────────────────────────────────────────────

function KnowledgeGraph() {
  const ref    = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })

  const domains = [
    { name: 'Software',    color: C.brand,   cx: 340, cy: 88,  r: 38 },
    { name: 'Finance',     color: C.gold,    cx: 375, cy: 228, r: 30 },
    { name: 'Healthcare',  color: '#5F9E72', cx: 298, cy: 358, r: 26 },
    { name: 'Design',      color: '#9B6BC9', cx: 112, cy: 358, r: 28 },
    { name: 'Data Science',color: '#3B87D0', cx: 38,  cy: 198, r: 34 },
    { name: 'Marketing',   color: '#C97B3A', cx: 118, cy: 68,  r: 25 },
  ]
  const px = 210, py = 212

  return (
    <div ref={ref} style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg viewBox="0 0 420 430" style={{ width: '100%', maxWidth: '400px', height: 'auto' }}>
        {/* Orbit rings */}
        {[130, 165].map((r, i) => (
          <circle
            key={i} cx={px} cy={py} r={r}
            fill="none"
            stroke="rgba(13,31,31,0.05)"
            strokeWidth="1"
            strokeDasharray="4 8"
          />
        ))}

        {/* Connection lines */}
        {domains.map((d, i) => (
          <motion.line
            key={`l${i}`}
            x1={px} y1={py} x2={d.cx} y2={d.cy}
            stroke={d.color}
            strokeWidth="1.5"
            strokeOpacity="0.40"
            strokeDasharray="6 5"
            initial={{ pathLength: 0 }}
            animate={inView ? { pathLength: 1 } : {}}
            transition={{ duration: 0.7, delay: 0.4 + i * 0.08 }}
          />
        ))}

        {/* Domain bubbles */}
        {domains.map((d, i) => (
          <g key={`d${i}`}>
            <motion.circle
              cx={d.cx} cy={d.cy} r={d.r + 10}
              fill={d.color} fillOpacity="0.06"
              stroke={d.color} strokeWidth="1" strokeOpacity="0.15"
              initial={{ scale: 0 }}
              animate={inView ? { scale: 1 } : {}}
              transition={{ duration: 0.5, delay: 0.7 + i * 0.1 }}
            />
            <motion.circle
              cx={d.cx} cy={d.cy} r={d.r}
              fill={d.color} fillOpacity="0.14"
              stroke={d.color} strokeWidth="1.5" strokeOpacity="0.60"
              initial={{ scale: 0 }}
              animate={inView ? { scale: 1 } : {}}
              transition={{ duration: 0.5, delay: 0.6 + i * 0.1, type: 'spring', stiffness: 180 }}
            />
            <motion.text
              x={d.cx} y={d.cy + 4}
              textAnchor="middle"
              fontSize={d.r >= 34 ? 9 : 8}
              fill={d.color}
              fontWeight="700"
              letterSpacing="0.04em"
              initial={{ opacity: 0 }}
              animate={inView ? { opacity: 1 } : {}}
              transition={{ duration: 0.4, delay: 0.9 + i * 0.08 }}
            >
              {d.name}
            </motion.text>
          </g>
        ))}

        {/* Person — pulse ring */}
        <motion.circle
          cx={px} cy={py} r={50}
          fill="none" stroke={C.gold} strokeWidth="1" strokeOpacity="0.30"
          animate={{ r: [50, 60, 50], opacity: [0.30, 0.08, 0.30] }}
          transition={{ duration: 2.8, repeat: Infinity, ease: 'easeInOut' }}
        />
        {/* Person — base circle */}
        <motion.circle
          cx={px} cy={py} r={32}
          fill={C.goldSubtle} stroke={C.gold} strokeWidth="2"
          initial={{ scale: 0 }}
          animate={inView ? { scale: 1 } : {}}
          transition={{ duration: 0.6, delay: 0.3, type: 'spring', stiffness: 200 }}
        />
        {/* Head */}
        <motion.circle
          cx={px} cy={py - 13} r={8}
          fill={C.gold}
          initial={{ scale: 0 }}
          animate={inView ? { scale: 1 } : {}}
          transition={{ duration: 0.4, delay: 0.5 }}
        />
        {/* Body */}
        <motion.path
          d={`M${px} ${py - 5} L${px - 10} ${py + 17} M${px} ${py - 5} L${px + 10} ${py + 17}`}
          stroke={C.gold} strokeWidth="2.5" strokeLinecap="round" fill="none"
          initial={{ pathLength: 0 }}
          animate={inView ? { pathLength: 1 } : {}}
          transition={{ duration: 0.4, delay: 0.6 }}
        />
        {/* You label */}
        <motion.text
          x={px} y={py + 52}
          textAnchor="middle" fontSize="9"
          fill={C.gold} fontWeight="700" letterSpacing="0.1em"
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ delay: 0.8 }}
        >
          YOU
        </motion.text>
      </svg>
    </div>
  )
}

// ─── Market Signal ────────────────────────────────────────────────────────────

function Counter({ to, suffix = '' }: { to: number; suffix?: string }) {
  const ref    = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: false })
  const active = useRef(false)

  useEffect(() => {
    if (!inView) return
    active.current = true

    function animate(ts0: number) {
      function tick(ts: number) {
        if (!active.current) return
        const t = Math.min((ts - ts0) / 1800, 1)
        const eased = 1 - Math.pow(1 - t, 3)
        if (ref.current) ref.current.textContent = Math.round(eased * to).toLocaleString() + suffix
        if (t < 1) {
          requestAnimationFrame(tick)
        } else {
          setTimeout(() => {
            if (!active.current) return
            if (ref.current) ref.current.textContent = '0' + suffix
            requestAnimationFrame(animate)
          }, 3500)
        }
      }
      tick(ts0)
    }

    requestAnimationFrame(animate)
    return () => { active.current = false }
  }, [inView, to, suffix])

  return <span ref={ref}>0{suffix}</span>
}

function MarketSignalSection() {
  return (
    <section id="market-signal" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', minHeight: '100vh' }}>
      {/* Left — dark, stats + rolling ticker */}
      <div style={{
        background:    C.dark,
        padding:       '80px clamp(24px, 5vw, 72px)',
        display:       'flex',
        flexDirection: 'column',
        justifyContent:'center',
      }}>
        {/* Live indicator */}
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

        {/* Rolling stats */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '40px', marginBottom: '56px' }}>
          {[
            { to: 2847, suffix: '',  label: 'jobs ingested in the last 24 hours',        color: '#FFFFFF' },
            { to: 14,   suffix: '',  label: 'role clusters mapped across all industries', color: '#FFFFFF' },
            { to: 89,   suffix: '%', label: 'average match accuracy',                     color: C.gold   },
          ].map((item, i) => (
            <div key={i}>
              <div style={{
                fontSize:     'clamp(2.5rem, 4vw, 4.5rem)',
                fontFamily:   'inherit',
                fontWeight:   400,
                color:        item.color,
                lineHeight:   1,
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

        {/* Ticker belt — white background, dark text, bigger font */}
        <div style={{
          overflow:     'hidden',
          background:   'rgba(255,255,255,0.97)',
          borderRadius: '12px',
          border:       '1px solid rgba(255,255,255,0.85)',
          padding:      '11px 0',
          boxShadow:    '0 2px 16px rgba(0,0,0,0.22)',
        }}>
          <div className="animate-ticker" style={{ display: 'flex', width: 'max-content', alignItems: 'center' }}>
            {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
              <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: '10px', padding: '0 22px' }}>
                <span style={{ fontSize: '15px', fontWeight: 500, color: C.textPrimary, whiteSpace: 'nowrap', fontFamily: 'inherit' }}>
                  {item}
                </span>
                <span style={{ color: C.gold, fontSize: '13px', fontWeight: 700 }}>·</span>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Right — light, knowledge graph */}
      <div style={{
        background:    C.base,
        padding:       '80px clamp(24px, 5vw, 72px)',
        display:       'flex',
        flexDirection: 'column',
        justifyContent:'center',
      }}>
        <div style={{ marginBottom: '12px' }}>
          <p style={{
            fontSize:      '11px',
            fontWeight:    600,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color:         C.brand,
            marginBottom:  '10px',
          }}>
            YOUR CAREER LANDSCAPE
          </p>
          <h2 style={{
            fontSize:     'clamp(1.6rem, 2.5vw, 2.2rem)',
            fontFamily:   'inherit',
            fontWeight:   400,
            color:        C.textPrimary,
            lineHeight:   1.2,
            marginBottom: '8px',
          }}>
            Every domain,<br />mapped to you.
          </h2>
          <p style={{ fontSize: '13px', color: C.textSecondary, lineHeight: 1.7, maxWidth: '320px' }}>
            See which clusters match your background — and which ones are one skill away.
          </p>
        </div>
        <KnowledgeGraph />
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
          fontFamily:   'inherit',
          fontWeight:   400,
          color:        C.textPrimary,
          textAlign:    'center',
          marginBottom: '80px',
          lineHeight:   1.15,
        }}>
          What happens after you upload.
        </h2>

        <div style={{ position: 'relative', height: '420px', maxWidth: '720px', margin: '0 auto 48px' }}>
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
          fontFamily:   'inherit',
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
    <div style={{ background: C.base, overflowX: 'hidden' }}>
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
