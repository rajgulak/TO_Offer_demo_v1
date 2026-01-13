/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'aa-red': '#D32F2F',
        'aa-blue': '#0D6EFD',
        'aa-navy': '#1A365D',
      },
      animation: {
        'pulse-glow': 'pulseGlow 1.5s ease-in-out infinite',
        'flow': 'flow 2s linear infinite',
        'slide-up': 'slideUp 0.4s ease-out',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(59, 130, 246, 0.4)' },
          '50%': { boxShadow: '0 0 0 12px rgba(59, 130, 246, 0)' },
        },
        flow: {
          '0%': { strokeDashoffset: '20' },
          '100%': { strokeDashoffset: '0' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
