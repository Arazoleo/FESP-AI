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

        ink: {
          DEFAULT: 'rgb(var(--ink-rgb) / <alpha-value>)',
          raise: 'rgb(var(--ink-raise-rgb) / <alpha-value>)',
          deep: 'rgb(var(--ink-deep-rgb) / <alpha-value>)',
        },

        paper: {
          DEFAULT: 'rgb(var(--paper-rgb) / <alpha-value>)',
          dim: 'rgb(var(--paper-dim-rgb) / <alpha-value>)',
          mute: 'rgb(var(--paper-mute-rgb) / <alpha-value>)',
        },

        accent: {
          DEFAULT: 'rgb(var(--accent-rgb) / <alpha-value>)',
          deep: 'rgb(var(--accent-deep-rgb) / <alpha-value>)',
          dark: 'rgb(var(--accent-dark-rgb) / <alpha-value>)',
        },

        line: {
          DEFAULT: 'rgb(var(--line-rgb) / var(--line-alpha))',
          strong: 'rgb(var(--line-rgb) / var(--line-strong-alpha))',
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
