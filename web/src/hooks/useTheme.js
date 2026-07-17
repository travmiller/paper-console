import { useEffect } from 'react';

export const THEME_OPTIONS = ['light', 'dark', 'system'];

// Mirrors the server-side theme setting so the inline script in index.html
// can apply it before first paint on the next load (no light-mode flash).
const STORAGE_KEY = 'pc1-theme';

const resolveTheme = (theme) =>
  theme === 'system'
    ? window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light'
    : theme;

/**
 * Applies the theme setting to <html data-theme="...">.
 * Pass undefined while settings are still loading — the pre-paint value
 * from localStorage stays in effect until the server value arrives.
 */
const useTheme = (theme) => {
  useEffect(() => {
    if (!theme) return undefined;
    const value = THEME_OPTIONS.includes(theme) ? theme : 'light';
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Private browsing / storage disabled — pre-paint falls back to light.
    }
    document.documentElement.dataset.theme = resolveTheme(value);

    if (value !== 'system') return undefined;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => {
      document.documentElement.dataset.theme = resolveTheme('system');
    };
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [theme]);
};

export default useTheme;
