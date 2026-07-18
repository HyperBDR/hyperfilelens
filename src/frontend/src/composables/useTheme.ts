import { ref, computed } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'hybrid'

const STORAGE_KEY = 'hfl-theme-mode'

const theme = ref<ThemeMode>('hybrid')

// Initialize from localStorage
try {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'hybrid') {
    theme.value = stored
  } else if (stored === 'light' || stored === 'dark') {
    localStorage.setItem(STORAGE_KEY, 'hybrid')
  }
} catch {
  /* ignore */
}

function setTheme(mode: ThemeMode) {
  theme.value = mode
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    /* ignore */
  }
  applyThemeToDOM(mode)
}

function applyThemeToDOM(mode: ThemeMode) {
  const root = document.documentElement
  root.setAttribute('data-theme', mode)
  // Toggle .dark class for Element Plus dark mode support
  if (mode === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
}

// Apply on load
applyThemeToDOM(theme.value)

export function useTheme() {
  const isLight = computed(() => theme.value === 'light')
  const isDark = computed(() => theme.value === 'dark')
  const isHybrid = computed(() => theme.value === 'hybrid')

  return {
    theme,
    isLight,
    isDark,
    isHybrid,
    setTheme,
  }
}
