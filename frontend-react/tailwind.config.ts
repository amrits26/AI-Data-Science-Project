import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Imperial Cars color system (WCAG 2.1 AA contrast verified)
        'imperial-primary':   '#1e3a5f', // Navy blue (main)
        'imperial-primary-light': '#3b6fa0', // Lighter blue (hover/highlight)
        'imperial-gold':      '#d4a843', // Gold accent
        'imperial-accent':    '#f0a500', // Amber accent (optional)
        'imperial-danger':    '#c92a2a', // Red (critical/urgent)
        'imperial-success':   '#2e7d32', // Green (success)
        'imperial-bg-light':  '#f8f9fa', // Near-white background
        'imperial-bg-dark':   '#121212', // Dark mode bg
        'imperial-surface':   '#ffffff', // Card surface (light)
        'imperial-surface-dark': '#1e1e1e', // Card surface (dark)
        'imperial-text':      '#1a1a1a', // Primary text (light)
        'imperial-text-dark': '#e8e8e8', // Primary text (dark)
        'imperial-text-secondary': '#6b7280', // Secondary text (light)
        'imperial-text-secondary-dark': '#9ca3af', // Secondary text (dark)
        'imperial-border':    '#e5e7eb', // Border (light)
        'imperial-border-dark': '#2d2d2d', // Border (dark)
      },
      fontFamily: {
        'sans': ['Inter', 'system-ui', 'Segoe UI', 'Roboto', 'Arial', 'Helvetica', 'sans-serif'],
      },
    },
  },
  darkMode: 'media', // Use prefers-color-scheme
  plugins: [],
}

export default config
