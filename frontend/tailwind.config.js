/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        serif: ['Newsreader', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'Menlo', 'Monaco', 'Courier New', 'monospace'],
      },
      colors: {
        notion: {
          bg: '#ffffff',
          sidebar: '#fbfbfa',
          hover: '#efefee',
          border: '#e8e8e6',
          darkBorder: '#d3d3d0',
          text: '#2f2f2f',
          subtext: '#787774',
          highlight: '#f1f1ef',
          callout: '#f7f6f3'
        }
      }
    },
  },
  plugins: [],
}
