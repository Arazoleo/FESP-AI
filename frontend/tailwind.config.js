/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Superfícies
        ink: {
          DEFAULT: '#0b0f0e',
          raise: '#101513',
          deep: '#070a09',
        },
        // Texto
        paper: {
          DEFAULT: '#ecf2ef',
          dim: '#9aa8a2',
          mute: '#7d8c86', // ≥4.5:1 sobre ink (5.5:1) e ink.raise (5.2:1) — WCAG 2.1 AA 1.4.3
        },
        // Acento único (verde-esmeralda)
        accent: {
          DEFAULT: '#34d399',
          deep: '#10b981',
          dark: '#0d9268',
        },
        // Linhas / bordas sutis
        line: {
          DEFAULT: 'rgba(236, 242, 239, 0.08)',
          strong: 'rgba(236, 242, 239, 0.14)',
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', 'sans-serif'],
        display: ['var(--font-display)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
      letterSpacing: {
        tightest: '-0.04em',
      },
    },
  },
  plugins: [],
}
