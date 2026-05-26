'use client'

import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Database, TrendingUp, Layers, X } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { mockClusters } from '@/lib/mockData'

const iconMap: Record<string, React.ElementType> = {
  Database,
  TrendingUp,
  Layers,
}

export default function ClusterOrbit() {
  const router = useRouter()
  const [selectedCluster, setSelectedCluster] = useState<typeof mockClusters[0] | null>(null)
  const [containerSize, setContainerSize] = useState({ width: 600, height: 600 })
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const update = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        setContainerSize({ width: rect.width, height: rect.height })
      }
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  const cx = containerSize.width / 2
  const cy = containerSize.height / 2
  const radius = Math.min(containerSize.width, containerSize.height) * 0.36

  const clusterPositions = mockClusters.map((cluster, i) => {
    const angle = (i / mockClusters.length) * 2 * Math.PI - Math.PI / 2
    return {
      ...cluster,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      phase: i * 1.1,
    }
  })

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Radial gradient background */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'radial-gradient(circle at center, rgba(139,26,26,0.04) 0%, transparent 70%)',
          pointerEvents: 'none',
        }}
      />

      {/* SVG connection lines */}
      <svg
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
      >
        {clusterPositions.map((cluster) => (
          <motion.line
            key={`line-${cluster.id}`}
            x1={cx}
            y1={cy}
            x2={cluster.x}
            y2={cluster.y}
            stroke={selectedCluster?.id === cluster.id ? '#8B1A1A' : '#D4D0C8'}
            strokeWidth="1.5"
            strokeDasharray="6 4"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ delay: 0.4 + Number(cluster.id) * 0.15, duration: 0.6, ease: 'easeOut' }}
          />
        ))}
      </svg>

      {/* Center "You" node */}
      <motion.div
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 300, damping: 25, delay: 0.1 }}
        style={{
          position: 'absolute',
          left: cx - 44,
          top: cy - 44,
          width: 88,
          height: 88,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 10,
        }}
      >
        {/* Pulsing ring */}
        <motion.div
          animate={{ scale: [1, 1.6], opacity: [0.3, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeOut' }}
          style={{
            position: 'absolute',
            width: 80,
            height: 80,
            borderRadius: '50%',
            border: '2px solid #8B1A1A',
          }}
        />
        <div
          style={{
            width: 72,
            height: 72,
            borderRadius: '50%',
            background: 'white',
            border: '2px solid #8B1A1A',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 16px rgba(139,26,26,0.12)',
          }}
        >
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#8B1A1A' }}>YOU</span>
        </div>
        <span
          style={{
            marginTop: '8px',
            fontSize: '11px',
            color: '#6B6B6B',
            fontWeight: 500,
            whiteSpace: 'nowrap',
          }}
        >
          Your Profile
        </span>
      </motion.div>

      {/* Cluster nodes */}
      {clusterPositions.map((cluster, i) => {
        const Icon = iconMap[cluster.icon] ?? Database
        const isSelected = selectedCluster?.id === cluster.id
        return (
          <motion.div
            key={cluster.id}
            initial={{ scale: 0, opacity: 0 }}
            animate={{
              scale: 1,
              opacity: 1,
              y: [0, -6, 0],
            }}
            transition={{
              scale: { type: 'spring', stiffness: 280, damping: 22, delay: 0.6 + i * 0.15 },
              opacity: { delay: 0.6 + i * 0.15, duration: 0.3 },
              y: {
                duration: 3,
                repeat: Infinity,
                ease: 'easeInOut',
                delay: cluster.phase,
                repeatType: 'reverse',
              },
            }}
            onClick={() => setSelectedCluster(isSelected ? null : cluster)}
            style={{
              position: 'absolute',
              left: cluster.x - 50,
              top: cluster.y - 50,
              width: 100,
              height: 100,
              cursor: 'pointer',
              zIndex: 5,
            }}
            whileHover={{ scale: 1.08 }}
          >
            <div
              style={{
                width: '100%',
                height: '100%',
                borderRadius: '50%',
                background: 'white',
                border: `2px solid ${isSelected ? '#8B1A1A' : '#E8E6E1'}`,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '4px',
                boxShadow: isSelected
                  ? '0 4px 24px rgba(139,26,26,0.18)'
                  : '0 2px 12px rgba(0,0,0,0.06)',
                transition: 'border-color 0.2s, box-shadow 0.2s',
              }}
            >
              <Icon size={20} color={isSelected ? '#8B1A1A' : '#6B6B6B'} />
              <span style={{ fontSize: '10px', fontWeight: 700, color: '#1A1A1A', textAlign: 'center', lineHeight: 1.2, padding: '0 8px' }}>
                {cluster.name}
              </span>
              <span style={{ fontSize: '10px', fontWeight: 600, color: '#8B1A1A' }}>
                {cluster.fit}% match
              </span>
            </div>
          </motion.div>
        )
      })}

      {/* Bottom sheet when cluster selected */}
      <AnimatePresence>
        {selectedCluster && (
          <motion.div
            initial={{ y: '100%', opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: '100%', opacity: 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 35 }}
            style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              background: 'white',
              borderRadius: '20px 20px 0 0',
              border: '1px solid #E8E6E1',
              borderBottom: 'none',
              padding: '24px',
              zIndex: 20,
              boxShadow: '0 -8px 32px rgba(0,0,0,0.08)',
            }}
          >
            <button
              onClick={() => setSelectedCluster(null)}
              style={{
                position: 'absolute',
                top: '16px',
                right: '16px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#6B6B6B',
              }}
            >
              <X size={16} />
            </button>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginBottom: '8px' }}>
              <h3 style={{ fontSize: '20px', fontWeight: 700, color: '#1A1A1A', letterSpacing: '-0.02em' }}>
                {selectedCluster.name}
              </h3>
              <span style={{ fontSize: '14px', fontWeight: 600, color: '#8B1A1A' }}>
                {selectedCluster.fit}% match
              </span>
            </div>

            <div style={{ display: 'flex', gap: '20px', marginBottom: '20px' }}>
              <div>
                <p style={{ fontSize: '11px', color: '#6B6B6B', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px' }}>
                  You have
                </p>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {selectedCluster.skills_present.map((s) => (
                    <span key={s} style={{ fontSize: '12px', background: '#F0E4C2', color: '#8B1A1A', padding: '3px 10px', borderRadius: '9999px', fontWeight: 500 }}>
                      {s}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <p style={{ fontSize: '11px', color: '#6B6B6B', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px' }}>
                  Gap
                </p>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {selectedCluster.skills_missing.map((s) => (
                    <span key={s} style={{ fontSize: '12px', background: '#F8F7F4', color: '#6B6B6B', padding: '3px 10px', borderRadius: '9999px', fontWeight: 500, border: '1px solid #E8E6E1' }}>
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={() => router.push('/plan')}
                style={{
                  flex: 1,
                  background: '#8B1A1A',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '12px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#B94040' }}
                onMouseLeave={(e) => { e.currentTarget.style.background = '#8B1A1A' }}
              >
                Build my plan →
              </button>
              <button
                onClick={() => setSelectedCluster(null)}
                style={{
                  padding: '12px 20px',
                  background: 'none',
                  border: '1px solid #E8E6E1',
                  borderRadius: '8px',
                  fontSize: '14px',
                  color: '#6B6B6B',
                  cursor: 'pointer',
                  fontWeight: 500,
                }}
              >
                Explore another
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
