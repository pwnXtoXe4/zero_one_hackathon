/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#F3F4F2', // app background (quiet warm grey)
        surface: '#FFFFFF', // cards
        surface2: '#ECEEEB', // insets / wells
        border: '#D7DAD5', // hairlines
        ink: '#171C19', // primary text
        muted: '#626B66', // secondary text
        signal: '#158765', // long / positive
        amber: '#B7791F', // short / shock / warning
        danger: '#B91C1C', // down
        cool: '#2F5E8F', // forecast / spot
      },
      fontFamily: {
        display: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Consolas', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 1px rgba(23,28,25,0.04)',
        raised: '0 8px 24px -18px rgba(23,28,25,0.36)',
      },
    },
  },
  plugins: [],
}
