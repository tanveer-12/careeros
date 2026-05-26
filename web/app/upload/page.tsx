'use client'

import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { UploadCloud, CheckCircle } from 'lucide-react'

const steps = [
  'Extracting skills...',
  'Reading experience signals...',
  'Mapping to live clusters...',
]

export default function UploadPage() {
  const router = useRouter()
  const [file, setFile] = useState<File | null>(null)
  const [parsing, setParsing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [completedSteps, setCompletedSteps] = useState<number[]>([])
  const [done, setDone] = useState(false)

  const simulateParsing = () => {
    setParsing(true)
    const interval = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) {
          clearInterval(interval)
          return 100
        }
        return p + 2
      })
    }, 50)

    setTimeout(() => setCompletedSteps([0]), 700)
    setTimeout(() => setCompletedSteps([0, 1]), 1400)
    setTimeout(() => {
      setCompletedSteps([0, 1, 2])
      setDone(true)
    }, 2500)
  }

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const f = acceptedFiles[0]
    if (f) {
      setFile(f)
      simulateParsing()
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'] },
    maxFiles: 1,
    disabled: parsing,
  })

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#F8F7F4',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px 24px 120px',
      }}
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        style={{ width: '100%', maxWidth: '560px' }}
      >
        <h1 style={{
          fontSize: 'clamp(2rem, 4vw, 2.75rem)',
          fontWeight: 700,
          letterSpacing: '-0.03em',
          color: '#1A1A1A',
          marginBottom: '8px',
        }}>
          Drop your resume.
        </h1>
        <p style={{ fontSize: '18px', color: '#6B6B6B', marginBottom: '40px' }}>
          We&apos;ll handle the rest.
        </p>

        {/* Dropzone */}
        <div
          {...getRootProps()}
          style={{
            border: `2px dashed ${isDragActive ? '#8B1A1A' : '#D4D0C8'}`,
            borderRadius: '16px',
            padding: '64px 32px',
            textAlign: 'center',
            cursor: parsing ? 'default' : 'pointer',
            background: isDragActive ? '#F0E4C2' : 'white',
            transition: 'all 0.2s ease',
            marginBottom: '32px',
          }}
          onMouseEnter={(e) => {
            if (!parsing && !isDragActive) {
              e.currentTarget.style.borderColor = '#8B1A1A'
              e.currentTarget.style.background = 'rgba(240,228,194,0.3)'
            }
          }}
          onMouseLeave={(e) => {
            if (!parsing && !isDragActive) {
              e.currentTarget.style.borderColor = '#D4D0C8'
              e.currentTarget.style.background = 'white'
            }
          }}
        >
          <input {...getInputProps()} />
          <UploadCloud size={40} color="#8B1A1A" style={{ margin: '0 auto 16px' }} />
          {file ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <CheckCircle size={18} color="#8B1A1A" />
              <span style={{ fontSize: '15px', fontWeight: 600, color: '#1A1A1A' }}>{file.name}</span>
            </div>
          ) : (
            <>
              <p style={{ fontSize: '15px', color: '#6B6B6B', marginBottom: '8px' }}>
                {isDragActive ? 'Drop it here' : 'Drag and drop your resume, or click to browse'}
              </p>
              <p style={{ fontSize: '12px', color: '#6B6B6B', opacity: 0.7 }}>PDF or DOCX</p>
            </>
          )}
        </div>

        {/* Progress */}
        <AnimatePresence>
          {parsing && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              {/* Progress bar */}
              <div
                style={{
                  height: '4px',
                  background: '#E8E6E1',
                  borderRadius: '9999px',
                  overflow: 'hidden',
                  marginBottom: '24px',
                }}
              >
                <motion.div
                  initial={{ width: '0%' }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.1 }}
                  style={{
                    height: '100%',
                    background: '#8B1A1A',
                    borderRadius: '9999px',
                  }}
                />
              </div>

              {/* Step items */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '32px' }}>
                {steps.map((step, i) => (
                  <AnimatePresence key={i}>
                    {completedSteps.includes(i) && (
                      <motion.div
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.3 }}
                        style={{ display: 'flex', alignItems: 'center', gap: '10px' }}
                      >
                        <CheckCircle size={16} color="#8B1A1A" />
                        <span style={{ fontSize: '14px', color: '#6B6B6B' }}>{step}</span>
                      </motion.div>
                    )}
                  </AnimatePresence>
                ))}
              </div>

              {/* Done button */}
              <AnimatePresence>
                {done && (
                  <motion.button
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                    onClick={() => router.push('/clusters')}
                    style={{
                      width: '100%',
                      background: '#8B1A1A',
                      color: 'white',
                      border: 'none',
                      borderRadius: '8px',
                      padding: '14px',
                      fontSize: '16px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'background 0.2s',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = '#B94040' }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = '#8B1A1A' }}
                  >
                    See where you fit →
                  </motion.button>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
