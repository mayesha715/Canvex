/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Geist', 'system-ui', 'sans-serif'],
        handwriting: ['Caveat', 'cursive'],
        'reading-serif': ['Literata', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(148, 163, 184, 0.2), 0 20px 45px -25px rgba(15, 23, 42, 0.6)',
        glass: 'inset 0 1px 0 rgba(255, 255, 255, 0.08)',
      },
    },
  },
  plugins: [],
}
