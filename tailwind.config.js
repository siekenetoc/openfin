/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './**/templates/**/*.html',
    './static/src/js/**/*.js',
    './**/forms.py'
  ],
  theme: {
    extend: {
      colors: {
        gray: {
          750: '#262f3f',
          850: '#161d2a',
          950: '#0b0f17'
        },
        brand: {
          50: '#effcf9',
          100: '#c8f7ec',
          200: '#91eeda',
          300: '#53ddc4',
          400: '#25c4ab',
          500: '#12a891',
          600: '#0b8776',
          700: '#0d6b60',
          800: '#0f554e',
          900: '#104741'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace']
      },
      boxShadow: {
        soft: '0 10px 30px -12px rgba(0,0,0,.45)'
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography')
  ]
};
