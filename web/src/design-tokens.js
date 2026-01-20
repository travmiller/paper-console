/**
 * Design Tokens for PC-1 Paper Console
 * 
 * Common class compositions for reuse.
 * Colors are defined in tailwind.config.js and used directly as Tailwind classes.
 */

// Common class combinations for reuse
export const commonClasses = {
  // Input fields
  input: 'w-full p-3 text-base bg-white border-2 border-zinc-300 rounded-lg text-black focus:border-black focus:outline-none ',
  inputSmall: 'w-full p-2 text-sm bg-white border-2 border-zinc-300 rounded-lg text-black focus:border-black focus:outline-none ',

  // Labels
  label: 'block mb-2 text-sm text-black  font-bold',
  labelSmall: 'block mb-1 text-xs text-black  font-bold',

  // Cards
  card: 'bg-white border-2 border-zinc-300 rounded-lg p-4',
  cardNested: 'bg-zinc-50 p-3 rounded-lg border-2 border-zinc-300',
  cardNestedSmall: 'bg-zinc-50 p-2 rounded-lg border-2 border-zinc-300',

  // Buttons
  buttonPrimary: 'px-6 py-2 bg-transparent border-2 border-black text-black  font-bold rounded-lg hover:bg-black hover:text-white transition-all cursor-pointer',
  buttonSecondary: 'px-4 py-2 bg-transparent border-2 border-zinc-400 hover:border-black rounded-lg text-black  transition-colors cursor-pointer hover-shimmer',
  buttonDanger: 'px-4 py-2 text-xs bg-transparent border-2 border-red-500 text-red-600 rounded-lg hover:bg-red-600 hover:text-white  font-bold transition-colors cursor-pointer',
  buttonGhost: 'text-xs px-2 py-0.5 rounded border-2 bg-transparent text-zinc-500 border-zinc-400 hover:text-black hover:border-black  transition-colors cursor-pointer hover-shimmer',

  // Modal
  modalBackdrop: 'fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4',
  modalContent: 'bg-white border-4 border-black rounded-xl p-4 sm:p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-lg',

  // Text helpers
  textMuted: 'text-zinc-600 text-sm ',
  textSubtle: 'text-xs text-zinc-500 ',
};

