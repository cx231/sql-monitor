import { defineStore } from 'pinia';

const THEME_STORAGE_KEY = 'sqlmon.theme_mode';

export type ThemeMode = 'light' | 'dark';

function readStoredTheme(): ThemeMode {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  return stored === 'dark' ? 'dark' : 'light';
}

function applyTheme(mode: ThemeMode): void {
  document.documentElement.dataset.theme = mode;
}

export const useThemeStore = defineStore('theme', {
  state: () => ({
    mode: readStoredTheme() as ThemeMode,
  }),
  actions: {
    initialize() {
      applyTheme(this.mode);
    },
    setMode(mode: ThemeMode) {
      this.mode = mode;
      localStorage.setItem(THEME_STORAGE_KEY, mode);
      applyTheme(mode);
    },
    toggleMode() {
      this.setMode(this.mode === 'light' ? 'dark' : 'light');
    },
  },
});

export { THEME_STORAGE_KEY };
