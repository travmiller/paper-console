/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', '"Helvetica Neue"', 'Arial', 'sans-serif'],
        mono: ['"IBM Plex Mono"', '"SF Mono"', '"Consolas"', '"Monaco"', '"Menlo"', '"Roboto Mono"', '"Courier New"', 'monospace'],
      },
      colors: {
        // Synth Theme Base
        bg: {
          base: '#131318',      // Deepest blue-black
          card: '#1a1b26',      // Panel background
          nested: '#131318',    // Nested items (same as base for cutout effect)
          input: '#252630',     // Input fields
          hover: '#2d2e3a',     // Hover state
        },
        // Synth Theme Accents
        synth: {
          border: '#8b8bf5',    // Periwinkle/Lavender Outline
          primary: '#ff3366',   // Neon Red/Pink
          secondary: '#00ff99', // Cyan/Green
          text: '#e0e0e0',      // Off-white text
          label: '#8b8bf5',     // Lavender labels
        },
        // Legacy status mapping (keeping for compatibility, but tweaked)
        status: {
          online: {
            DEFAULT: '#00ff99',
            bg: 'rgba(0, 255, 153, 0.1)',
            border: '#00ff99',
          },
          offline: {
            DEFAULT: '#8b8bf5',
            bg: 'rgba(139, 139, 245, 0.1)',
          },
          error: {
            DEFAULT: '#ff3366',
            bg: 'rgba(255, 51, 102, 0.1)',
            hover: 'rgba(255, 51, 102, 0.2)',
          },
        },
      },
    },
  },
  plugins: [],
};
// Force reload