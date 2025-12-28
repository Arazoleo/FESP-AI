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
        primary: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
          950: '#052e16',
        },
        unifesp: {
          light: '#22c55e',
          DEFAULT: '#16a34a',
          dark: '#15803d',
          darker: '#166534',
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'fade-in-up': 'fadeInUp 0.5s ease-out',
        'fade-in-down': 'fadeInDown 0.5s ease-out',
        'slide-in-right': 'slideInRight 0.4s ease-out',
        'slide-in-left': 'slideInLeft 0.4s ease-out',
        'scale-in': 'scaleIn 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce-slow': 'bounce 2s infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'gradient': 'gradient 8s ease infinite',
        // Novas animações ultra-sophisticated
        'dramatic-entrance': 'dramatic-entrance 1.2s cubic-bezier(0.25, 0.46, 0.45, 0.94)',
        'morphing-blob': 'morphing-blob 8s ease-in-out infinite',
        'liquid-float': 'liquid-float 6s ease-in-out infinite',
        'holographic': 'holographic 4s linear infinite',
        'particle-float': 'particle-float 15s linear infinite',
        'typing': 'typing 3.5s steps(40, end), blink-caret 0.75s step-end infinite',
        'magnetic-pull': 'magnetic-pull 0.6s ease-out',
        'ripple': 'ripple 0.6s linear',
        'gradient-shift': 'gradient-shift 3s ease infinite',
        'stagger-fade-in': 'stagger-fade-in 0.8s ease-out',
        'bounce-in': 'bounce-in 0.8s cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        'aurora': 'aurora-borealis 6s ease-in-out infinite',
        'prism': 'prism-effect 5s linear infinite',
        // Animações de entrada sequenciais
        'stagger-1': 'stagger-fade-in 0.8s ease-out 0.1s both',
        'stagger-2': 'stagger-fade-in 0.8s ease-out 0.2s both',
        'stagger-3': 'stagger-fade-in 0.8s ease-out 0.3s both',
        'stagger-4': 'stagger-fade-in 0.8s ease-out 0.4s both',
        'stagger-5': 'stagger-fade-in 0.8s ease-out 0.5s both',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeInDown: {
          '0%': { opacity: '0', transform: 'translateY(-20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        slideInLeft: {
          '0%': { opacity: '0', transform: 'translateX(-20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.9)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-1000px 0' },
          '100%': { backgroundPosition: '1000px 0' },
        },
        gradient: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        // Novos keyframes ultra-sophisticated
        'dramatic-entrance': {
          '0%': { opacity: '0', transform: 'scale(0.8) translateY(50px) rotateX(15deg)', filter: 'blur(10px)' },
          '60%': { opacity: '0.8', transform: 'scale(1.05) translateY(-5px) rotateX(0deg)', filter: 'blur(2px)' },
          '100%': { opacity: '1', transform: 'scale(1) translateY(0px) rotateX(0deg)', filter: 'blur(0px)' },
        },
        'morphing-blob': {
          '0%, 100%': { borderRadius: '60% 40% 30% 70% / 60% 30% 70% 40%' },
          '25%': { borderRadius: '30% 60% 70% 40% / 50% 60% 30% 60%' },
          '50%': { borderRadius: '50% 40% 30% 60% / 30% 60% 70% 40%' },
          '75%': { borderRadius: '40% 60% 50% 30% / 70% 40% 60% 50%' },
        },
        'liquid-float': {
          '0%, 100%': { transform: 'translateY(0px) rotate(0deg)' },
          '33%': { transform: 'translateY(-20px) rotate(2deg)' },
          '66%': { transform: 'translateY(-10px) rotate(-1deg)' },
        },
        'holographic': {
          '0%, 100%': { backgroundPosition: '0% 50%', filter: 'hue-rotate(0deg) brightness(1)' },
          '25%': { backgroundPosition: '100% 50%', filter: 'hue-rotate(15deg) brightness(1.1)' },
          '50%': { backgroundPosition: '100% 100%', filter: 'hue-rotate(30deg) brightness(1.2)' },
          '75%': { backgroundPosition: '0% 100%', filter: 'hue-rotate(15deg) brightness(1.1)' },
        },
        'particle-float': {
          '0%': { transform: 'translateY(100vh) rotate(0deg)', opacity: '0' },
          '10%': { opacity: '1' },
          '90%': { opacity: '1' },
          '100%': { transform: 'translateY(-100px) rotate(360deg)', opacity: '0' },
        },
        'typing': {
          'from': { width: '0' },
          'to': { width: '100%' },
        },
        'blink-caret': {
          'from, to': { borderColor: 'transparent' },
          '50%': { borderColor: 'currentColor' },
        },
        'magnetic-pull': {
          '0%': { transform: 'scale(1) translate(0, 0)' },
          '50%': { transform: 'scale(1.05) translate(2px, -2px)' },
          '100%': { transform: 'scale(1) translate(0, 0)' },
        },
        'ripple': {
          '0%': { transform: 'scale(0)', opacity: '1' },
          '100%': { transform: 'scale(4)', opacity: '0' },
        },
        'gradient-shift': {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
        'stagger-fade-in': {
          '0%': { opacity: '0', transform: 'translateY(30px) scale(0.95)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'bounce-in': {
          '0%': { opacity: '0', transform: 'scale(0.3) translateY(50px)' },
          '60%': { opacity: '1', transform: 'scale(1.1) translateY(-5px)' },
          '80%': { transform: 'scale(0.95) translateY(2px)' },
          '100%': { opacity: '1', transform: 'scale(1) translateY(0)' },
        },
        'aurora-borealis': {
          '0%, 100%': {
            background: 'linear-gradient(45deg, rgba(34, 197, 94, 0.1) 0%, rgba(74, 222, 128, 0.2) 25%, rgba(34, 197, 94, 0.1) 50%, rgba(21, 128, 61, 0.15) 75%, rgba(34, 197, 94, 0.1) 100%)'
          },
          '50%': {
            background: 'linear-gradient(45deg, rgba(74, 222, 128, 0.2) 0%, rgba(34, 197, 94, 0.3) 25%, rgba(74, 222, 128, 0.2) 50%, rgba(34, 197, 94, 0.25) 75%, rgba(74, 222, 128, 0.2) 100%)'
          },
        },
        'prism-effect': {
          '0%': { backgroundPosition: '0% 50%', filter: 'hue-rotate(0deg) saturate(1)' },
          '25%': { backgroundPosition: '100% 50%', filter: 'hue-rotate(90deg) saturate(1.2)' },
          '50%': { backgroundPosition: '100% 100%', filter: 'hue-rotate(180deg) saturate(1.4)' },
          '75%': { backgroundPosition: '0% 100%', filter: 'hue-rotate(270deg) saturate(1.2)' },
          '100%': { backgroundPosition: '0% 50%', filter: 'hue-rotate(360deg) saturate(1)' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'gradient-unifesp': 'linear-gradient(135deg, #16a34a 0%, #22c55e 50%, #4ade80 100%)',
      },
      boxShadow: {
        'glow': '0 0 20px rgba(34, 197, 94, 0.3)',
        'glow-lg': '0 0 30px rgba(34, 197, 94, 0.4)',
        'glow-xl': '0 0 40px rgba(34, 197, 94, 0.5), 0 0 80px rgba(34, 197, 94, 0.2)',
        'glow-2xl': '0 0 60px rgba(34, 197, 94, 0.6), 0 0 120px rgba(34, 197, 94, 0.3)',
        'holographic': '0 0 20px rgba(34, 197, 94, 0.3), inset 0 0 20px rgba(255, 255, 255, 0.1)',
        'glass': '0 8px 32px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
        'glass-dark': '0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
        'magnetic': '0 4px 20px rgba(34, 197, 94, 0.2), 0 0 0 1px rgba(34, 197, 94, 0.1)',
        'particle': '0 0 10px rgba(34, 197, 94, 0.5), 0 0 20px rgba(34, 197, 94, 0.2)',
      },
      backdropBlur: {
        xs: '2px',
      },
      filter: {
        'holographic': 'hue-rotate(15deg) brightness(1.1) saturate(1.2)',
        'aurora': 'brightness(1.2) saturate(1.3)',
      },
    },
  },
  plugins: [],
}

