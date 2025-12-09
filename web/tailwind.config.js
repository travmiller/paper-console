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
          nested: '#1a1a1a',    // Nested card/item backgrounds
          input: '#333',         // Input field backgrounds
          hover: '#444',        // Hover states
        },
        // Semantic colors
        status: {
          online: {
            DEFAULT: '#93c5fd',  // blue-300
            bg: 'rgba(59, 130, 246, 0.3)',    // blue-900/30
            border: 'rgba(30, 58, 138, 0.5)', // blue-900/50
          },
          offline: {
            DEFAULT: '#86efac',  // green-400
            bg: 'rgba(20, 83, 45, 0.4)',      // green-900/40
          },
          error: {
            DEFAULT: '#fca5a5',  // red-300
            bg: 'rgba(127, 29, 29, 0.3)',     // red-900/30
            hover: 'rgba(127, 29, 29, 0.5)',  // red-900/50
          },
        },
      },
    },
  },
  plugins: [],
};

