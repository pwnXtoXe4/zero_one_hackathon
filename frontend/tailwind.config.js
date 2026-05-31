/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#F4F7F5', // app background (quiet market terminal)
        surface: '#FFFFFF', // cards
        surface2: '#EEF4F1', // insets / wells
        border: '#D3DDD8', // hairlines
        ink: '#171C19', // primary text
        muted: '#5D6A64', // secondary text
        signal: '#009B72', // long / positive
        amber: '#D18500', // short / shock / warning
        danger: '#D6452E', // down
        cool: '#1E70B8', // forecast / spot
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
