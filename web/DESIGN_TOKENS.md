# Design Tokens & Color System

This document describes the centralized design token system for PC-1 Paper Console.

## Overview

The design system uses a centralized token system defined in `src/design-tokens.js` and Tailwind CSS configuration in `tailwind.config.js`. This ensures consistency across all components and makes it easy to update the color scheme globally.

## Usage

Import design tokens in your components:

```javascript
import { commonClasses, colors } from '../design-tokens';
```

## Color Palette

### Background Colors

- **`bg.base`** (`#242424`) - Main application background
- **`bg.card`** (`#2a2a2a`) - Card and modal backgrounds
- **`bg.nested`** (`#1a1a1a`) - Nested card/item backgrounds
- **`bg.input`** (`#333`) - Input field backgrounds
- **`bg.hover`** (`#444`) - Hover state backgrounds

### Text Colors

- **`text.primary`** (`white`) - Primary text color
- **`text.secondary`** (`gray-300`) - Secondary text
- **`text.muted`** (`gray-400`) - Muted text
- **`text.subtle`** (`gray-500`) - Subtle text
- **`text.disabled`** (`gray-600`) - Disabled text

### Border Colors

- **`border.default`** (`gray-700`) - Default borders
- **`border.light`** (`gray-600`) - Light borders
- **`border.dark`** (`gray-800`) - Dark borders
- **`border.hover`** (`white`) - Hover border color

### Semantic Colors

#### Online Status
- Background: `bg-blue-900/30`
- Text: `text-blue-300`
- Border: `border-blue-800`
- Hover: `hover:bg-blue-900/50`

#### Offline Status
- Background: `bg-green-900/40`
- Text: `text-green-400`

#### Error/Danger
- Background: `bg-red-900/30`
- Text: `text-red-300`
- Hover: `hover:bg-red-900/50`

#### Success
- Background: `bg-green-900/30`
- Text: `text-green-400`

## Common Classes

Pre-composed class combinations for common UI elements:

### Input Fields
- **`commonClasses.input`** - Standard input field
- **`commonClasses.inputSmall`** - Small input field

### Labels
- **`commonClasses.label`** - Standard label
- **`commonClasses.labelSmall`** - Small label

### Cards
- **`commonClasses.card`** - Standard card container
- **`commonClasses.cardNested`** - Nested card (with padding)
- **`commonClasses.cardNestedSmall`** - Small nested card

### Buttons
- **`commonClasses.buttonPrimary`** - Primary action button (white bg, black text)
- **`commonClasses.buttonSecondary`** - Secondary button (dark bg, white text)
- **`commonClasses.buttonDanger`** - Delete/danger button (red)
- **`commonClasses.buttonGhost`** - Ghost button (transparent)

### Modals
- **`commonClasses.modalBackdrop`** - Modal backdrop overlay
- **`commonClasses.modalContent`** - Modal content container

### Text Helpers
- **`commonClasses.textMuted`** - Muted text helper
- **`commonClasses.textSubtle`** - Subtle text helper

## Examples

### Using Common Classes

```javascript
// Input field
<input className={commonClasses.input} />

// Button
<button className={commonClasses.buttonPrimary}>Save</button>

// Card
<div className={commonClasses.cardNested}>
  <label className={commonClasses.labelSmall}>Item</label>
  <input className={commonClasses.inputSmall} />
</div>
```

### Using Color Tokens

```javascript
// Status badge
<span className={`${colors.status.online.bg} ${colors.status.online.text} px-2 py-1 rounded`}>
  Online
</span>

// Error button
<button className={`${colors.status.error.bg} ${colors.status.error.text} px-4 py-2 rounded`}>
  Delete
</button>
```

## Migration Guide

When refactoring existing components:

1. Replace hardcoded hex colors with token classes:
   - `bg-[#2a2a2a]` → `commonClasses.bg.card` or `commonClasses.card`
   - `text-gray-400` → `commonClasses.text.muted`
   - `border-gray-700` → `commonClasses.border.default`

2. Use common classes for repeated patterns:
   - Input fields → `commonClasses.input`
   - Buttons → `commonClasses.buttonPrimary` / `buttonSecondary` / etc.
   - Cards → `commonClasses.cardNested`

3. For semantic colors, use the status tokens:
   - Online badges → `colors.status.online.*`
   - Error states → `colors.status.error.*`

## Tailwind Config

The Tailwind configuration (`tailwind.config.js`) extends the default theme with custom colors that match our design tokens. These can be used directly in Tailwind classes:

```javascript
// Using Tailwind classes (if configured)
<div className="bg-bg-card text-text-primary">
```

However, for consistency, prefer using the `commonClasses` and `colors` from `design-tokens.js`.

## Future Enhancements

- Add spacing tokens
- Add typography tokens
- Add shadow/elevation tokens
- Add animation/transition tokens
- Support for light mode (when needed)

