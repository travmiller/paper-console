/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    fontFamily: {
      sans: ['"IBM Plex Sans"', 'sans-serif'],
      mono: ['"IBM Plex Mono"', 'monospace'],
    },
    extend: {
      colors: {
        // PC1 Theme Base
        bg: {
          base: '#131318',      // Deepest blue-black
          card: '#1a1b26',      // Panel background
          nested: '#131318',    // Nested items (same as base for cutout effect)
          input: '#252630',     // Input fields
          hover: '#2d2e3a',     // Hover state
        },
        // PC1 Theme Accents
        pc1: {
          border: '#2A2A2A',     // Soft Black Border
          primary: '#DC2626',    // Brand Red/Error
          secondary: '#ae861d',  // Brass/Gold
          text: '#2A2A2A',       // Soft Black Text
          label: '#6B665F',      // Muted label
        },
        // Status mapping
        status: {
          online: {
            DEFAULT: '#16a34a', // Brand Green
            bg: 'rgba(22, 163, 74, 0.1)',
            border: '#16a34a',
          },
          offline: {
            DEFAULT: '#6B665F',
            bg: 'rgba(107, 102, 95, 0.1)',
          },
          error: {
            DEFAULT: '#DC2626',
            bg: 'rgba(220, 38, 38, 0.1)',
            hover: 'rgba(220, 38, 38, 0.2)',
          },
        },
      },
    },
  },
  plugins: [],
};
// Force reload