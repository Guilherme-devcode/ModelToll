/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#eef7ff',
          100: '#d9edff',
          200: '#bbdfff',
          300: '#8dcbff',
          400: '#58adff',
          500: '#318bff',
          600: '#1a6af5',
          700: '#1453e1',
          800: '#1743b6',
          900: '#193b8f',
          950: '#142558',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
