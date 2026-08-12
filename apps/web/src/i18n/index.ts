import { create } from 'zustand'
import { LOCALES, type Locale, type Messages } from './messages'

const STORAGE_KEY = 'repocity.locale'

/**
 * Korean for Korean-speaking visitors, English for everyone else.
 *
 * The browser's language list already reflects where the visitor is and what they read,
 * and it travels with them; deriving it from an IP would be less accurate and would mean
 * asking a third party who the visitor is.
 */
export function detectLocale(): Locale {
  const stored = safeRead()
  if (stored) return stored

  const preferences = typeof navigator === 'undefined' ? [] : (navigator.languages ?? [])
  for (const tag of [...preferences, navigator?.language].filter(Boolean) as string[]) {
    if (tag.toLowerCase().startsWith('ko')) return 'ko'
  }
  return 'en'
}

function safeRead(): Locale | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'ko' || value === 'en' ? value : null
  } catch {
    return null
  }
}

function safeWrite(locale: Locale): void {
  try {
    localStorage.setItem(STORAGE_KEY, locale)
  } catch {
    // A blocked storage is not a reason to refuse to switch language.
  }
}

interface LocaleState {
  locale: Locale
  t: Messages
  setLocale: (locale: Locale) => void
}

export const useLocaleStore = create<LocaleState>((set) => {
  const locale = detectLocale()
  return {
    locale,
    t: LOCALES[locale],
    setLocale: (next) => {
      safeWrite(next)
      document.documentElement.lang = next
      set({ locale: next, t: LOCALES[next] })
    },
  }
})

/** Messages for the active locale. */
export const useT = (): Messages => useLocaleStore((state) => state.t)

export type { Locale, Messages }
