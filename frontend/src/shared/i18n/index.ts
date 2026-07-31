import { createI18n } from 'vue-i18n'

import en from './locales/en.json'
import tr from './locales/tr.json'

// Turkish is the default locale; English is fully supported from launch
// (REQ-NFR-I18N-001) — both ship together, not sequentially.
export const i18n = createI18n({
  legacy: false,
  locale: localStorage.getItem('locale') ?? 'tr',
  fallbackLocale: 'en',
  messages: { tr, en },
})

export function setLocale(locale: 'tr' | 'en') {
  i18n.global.locale.value = locale
  localStorage.setItem('locale', locale)
  document.documentElement.setAttribute('lang', locale)
}
