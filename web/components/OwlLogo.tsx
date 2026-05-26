interface OwlLogoProps {
  size?: number
  className?: string
}

export default function OwlLogo({ size = 32, className = '' }: OwlLogoProps) {
  const w = size * 0.6
  const h = size
  return (
    <svg
      width={w}
      height={h}
      viewBox="0 0 24 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Body — vertical stroke of L */}
      <rect x="2" y="0" width="14" height="34" rx="3" fill="#8B1A1A" />
      {/* Feet — horizontal base of L */}
      <rect x="2" y="30" width="22" height="6" rx="3" fill="#8B1A1A" />
      {/* Left eye */}
      <circle cx="8" cy="9" r="3.5" fill="#C9A84C" />
      {/* Right eye */}
      <circle cx="15" cy="9" r="3.5" fill="#C9A84C" />
      {/* Eye shine left */}
      <circle cx="9" cy="8" r="1" fill="white" opacity="0.6" />
      {/* Eye shine right */}
      <circle cx="16" cy="8" r="1" fill="white" opacity="0.6" />
    </svg>
  )
}
