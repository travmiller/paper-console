// Ink gradient colors (matching CSS variables)
const INK_BLACK = '#000000';        // --color-ink-black
const INK_GRAY_DARK = '#3a3a3a';    // --color-ink-gray-dark
const INK_GRAY_MEDIUM = '#4a4a4a';  // --color-ink-gray-medium
const INK_GRAY_LIGHT = '#525252';   // --color-ink-gray-light

// Ink-like gradients for card borders (printer ink simulation)
export const INK_GRADIENTS = [
  `radial-gradient(circle at 20% 30%, ${INK_BLACK} 0%, ${INK_GRAY_DARK} 25%, ${INK_BLACK} 50%, ${INK_GRAY_MEDIUM} 75%, ${INK_BLACK} 100%)`,
  `radial-gradient(circle at 80% 70%, ${INK_BLACK} 0%, ${INK_GRAY_MEDIUM} 20%, ${INK_BLACK} 40%, ${INK_GRAY_DARK} 60%, ${INK_BLACK} 80%, ${INK_GRAY_LIGHT} 100%)`,
  `radial-gradient(ellipse at 50% 20%, ${INK_BLACK} 0%, ${INK_GRAY_DARK} 30%, ${INK_BLACK} 60%, ${INK_GRAY_MEDIUM} 90%, ${INK_BLACK} 100%)`,
  `radial-gradient(circle at 70% 50%, ${INK_BLACK} 0%, ${INK_GRAY_LIGHT} 15%, ${INK_BLACK} 35%, ${INK_GRAY_DARK} 55%, ${INK_BLACK} 75%, ${INK_GRAY_MEDIUM} 100%)`,
  `radial-gradient(ellipse at 30% 80%, ${INK_BLACK} 0%, ${INK_GRAY_MEDIUM} 25%, ${INK_BLACK} 50%, ${INK_GRAY_DARK} 75%, ${INK_BLACK} 100%)`,
  `radial-gradient(circle at 60% 40%, ${INK_BLACK} 0%, ${INK_GRAY_DARK} 20%, ${INK_BLACK} 45%, ${INK_GRAY_LIGHT} 70%, ${INK_BLACK} 100%)`,
  `radial-gradient(ellipse at 40% 60%, ${INK_BLACK} 0%, ${INK_GRAY_MEDIUM} 30%, ${INK_BLACK} 60%, ${INK_GRAY_DARK} 90%, ${INK_BLACK} 100%)`,
  `radial-gradient(circle at 50% 50%, ${INK_BLACK} 0%, ${INK_GRAY_DARK} 25%, ${INK_BLACK} 50%, ${INK_GRAY_MEDIUM} 75%, ${INK_BLACK} 100%)`,
];
