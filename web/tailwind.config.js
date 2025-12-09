/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Base dark theme colors
        bg: {
          base: '#242424',      // Main background
          card: '#2a2a2a',      // Card/modal backgrounds
          nested: '#1a1a1a',     // Nested card/item backgrounds
          input: '#333',         // Input field backgrounds
          hover: '#444',         // Hover states
        },
        // Text colors
        text: {
          primary: '#ffffff',     // Primary text (white)
          secondary: 'rgba(255, 255, 255, 0.87)', // Secondary text
          muted: '#9ca3af',      // Muted text (gray-400)
          subtle: '#6b7280',    // Subtle text (gray-500)
          disabled: '#4b5563',  // Disabled text (gray-600)
        },
        // Border colors
        border: {
          default: '#374151',    // Default borders (gray-700)
          light: '#4b5563',      // Light borders (gray-600)
          dark: '#1f2937',       // Dark borders (gray-800)
          hover: '#ffffff',      // Hover border (white)
        },
        // Semantic colors
        status: {
          online: {
            bg: 'rgba(59, 130, 246, 0.3)',    // blue-900/30
            text: '#93c5fd',                    // blue-300
            border: 'rgba(30, 58, 138, 0.5)', // blue-900/50
          },
          offline: {
            bg: 'rgba(20, 83, 45, 0.4)',      // green-900/40
            text: '#86efac',                    // green-400
          },
          error: {
            bg: 'rgba(127, 29, 29, 0.3)',     // red-900/30
            text: '#fca5a5',                    // red-300
            hover: 'rgba(127, 29, 29, 0.5)',  // red-900/50
          },
          success: {
            bg: 'rgba(20, 83, 45, 0.3)',      // green-900/30
            text: '#86efac',                   // green-400
          },
        },
        // Interactive elements
        interactive: {
          primary: '#ffffff',
          primaryHover: '#e5e7eb',
          secondary: '#374151',
          secondaryHover: '#4b5563',
        },
      },
    },
  },
  plugins: [],
};

