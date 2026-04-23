import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        sidebar: '#171717',
        'sb-text': '#ececec',
        'sb-border': '#2e2e2e',
        accent: '#3b82f6',
      },
    },
  },
  plugins: [],
}
export default config
