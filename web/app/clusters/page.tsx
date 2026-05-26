import ClusterOrbit from '@/components/ClusterOrbit'

export default function ClustersPage() {
  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        background: '#F8F7F4',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        paddingBottom: '80px',
      }}
    >
      <div style={{ padding: '32px 48px 0', flexShrink: 0 }}>
        <p style={{
          fontSize: '12px',
          fontWeight: 500,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: '#C9A84C',
          marginBottom: '8px',
        }}>
          Your fit map
        </p>
        <h1 style={{
          fontSize: '28px',
          fontWeight: 700,
          letterSpacing: '-0.03em',
          color: '#1A1A1A',
        }}>
          Where you stand today.
        </h1>
      </div>
      <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        <ClusterOrbit />
      </div>
    </div>
  )
}
