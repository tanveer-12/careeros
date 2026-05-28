import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        base:           '#F5F6F4',
        surface:        '#FFFFFF',
        dark:           '#0D1F1F',
        'text-primary': '#0D1F1F',
        'text-secondary':'#4A6670',
        brand:          '#0A7C6E',
        'brand-hover':  '#0D9B8A',
        gold:           '#C9873A',
      },
      fontFamily: {
        sans:   ['var(--font-inter)',       'Inter',           'sans-serif'],
        serif:  ['var(--font-instrument)',  'Georgia',         'serif'],
      },
    },
  },
  plugins: [],
}

export default config
