/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#F5F7FA', // app background (soft cool grey)
        surface: '#FFFFFF', // cards
        surface2: '#F1F4F8', // insets / wells
        border: '#E4E8EF', // hairlines
        ink: '#0F172A', // primary text (slate-900)
        muted: '#64748B', // secondary text (slate-500)
        signal: '#0EA371', // long / positive (emerald)
        amber: '#D97706', // short / shock / warning
        danger: '#DC2626', // down
        cool: '#2563EB', // forecast / spot
      },
      fontFamily: {
        display: ['"Hanken Grotesk"', 'system-ui', 'sans-serif'],
        sans: ['"Hanken Grotesk"', 'system-ui', 'sans-serif'],
        mono: ['"Hanken Grotesk"', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(14,163,113,0.20), 0 12px 30px -16px rgba(14,163,113,0.25)',
        glowAmber: '0 0 0 1px rgba(217,119,6,0.28), 0 14px 36px -18px rgba(217,119,6,0.30)',
        card: '0 1px 2px rgba(16,24,40,0.04), 0 10px 24px -14px rgba(16,24,40,0.14)',
      },
      keyframes: {
        floaty: { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-6px)' } },
        pulseRing: {
          '0%': { boxShadow: '0 0 0 0 rgba(217,119,6,0.35)' },
          '100%': { boxShadow: '0 0 0 14px rgba(217,119,6,0)' },
        },
        scan: { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(200%)' } },
      },
      animation: {
        floaty: 'floaty 7s ease-in-out infinite',
        pulseRing: 'pulseRing 1.8s ease-out infinite',
      },
    },
  },
  plugins: [],
}
