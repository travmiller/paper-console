/**
 * Design Tokens for PC-1 Paper Console
 * 
 * Centralized color system and design constants.
 * Use these tokens instead of hardcoded colors for consistency.
 */

export const colors = {
  // Background colors
  bg: {
    base: 'bg-[#242424]',           // Main background
    card: 'bg-[#2a2a2a]',           // Card/modal backgrounds
    nested: 'bg-[#1a1a1a]',         // Nested card/item backgrounds
    input: 'bg-[#333]',              // Input field backgrounds
    hover: 'bg-[#444]',              // Hover states
  },
  
  // Text colors
  text: {
    primary: 'text-white',
    secondary: 'text-gray-300',
    muted: 'text-gray-400',
    subtle: 'text-gray-500',
    disabled: 'text-gray-600',
  },
  
  // Border colors
  border: {
    default: 'border-gray-700',
    light: 'border-gray-600',
    dark: 'border-gray-800',
    hover: 'border-white',
  },
  
  // Semantic colors
  status: {
    online: {
      bg: 'bg-blue-900/30',
      text: 'text-blue-300',
      border: 'border-blue-800',
      hover: 'hover:bg-blue-900/50',
    },
    offline: {
      bg: 'bg-green-900/40',
      text: 'text-green-400',
    },
    error: {
      bg: 'bg-red-900/30',
      text: 'text-red-300',
      hover: 'hover:bg-red-900/50',
    },
    success: {
      bg: 'bg-green-900/30',
      text: 'text-green-400',
    },
  },
  
  // Interactive elements
  button: {
    primary: 'bg-white text-black hover:bg-gray-200',
    secondary: 'bg-[#1a1a1a] border border-gray-600 hover:border-white text-white',
    danger: 'bg-red-900/20 text-red-400 border border-red-900/50 hover:bg-red-900/40',
    ghost: 'bg-transparent text-gray-400 hover:text-white border-gray-500 hover:border-gray-400',
  },
};

// Common class combinations for reuse
export const commonClasses = {
  // Input fields
  input: 'w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none',
  inputSmall: 'w-full p-2 text-sm bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none',
  
  // Labels
  label: 'block mb-2 text-sm text-gray-400',
  labelSmall: 'block mb-1 text-xs text-gray-400',
  
  // Cards
  card: 'bg-[#2a2a2a] border border-gray-700 rounded-md p-4',
  cardNested: 'bg-[#1a1a1a] p-3 rounded border border-gray-800',
  cardNestedSmall: 'bg-[#1a1a1a] p-2 rounded border border-gray-800',
  
  // Buttons
  buttonPrimary: 'px-6 py-2 bg-white text-black font-medium rounded hover:bg-gray-200 transition-colors',
  buttonSecondary: 'px-4 py-2 bg-[#1a1a1a] border border-gray-600 hover:border-white rounded text-white transition-colors',
  buttonDanger: 'px-2 py-1 text-xs bg-red-900/30 text-red-300 rounded hover:bg-red-900/50 transition-colors',
  buttonGhost: 'text-xs px-2 py-0.5 rounded border bg-transparent text-gray-300 border-gray-500 hover:text-white hover:border-gray-400 transition-colors',
  
  // Modal
  modalBackdrop: 'fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4',
  modalContent: 'bg-[#2a2a2a] border border-gray-700 rounded-lg p-4 sm:p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto',
  
  // Text helpers
  textMuted: 'text-gray-400 text-sm',
  textSubtle: 'text-xs text-gray-500',
};

