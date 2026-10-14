import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useEntityStore } from '@/shared/stores/entity'

export type ValueFormat = 'money' | 'number'

// Locale-aware formatting for everything the panel prints. The backend
// sends raw decimal strings and ISO dates; how they read (₺1.234,50 vs
// TRY 1,234.50, "Eki" vs "Oct") is decided here from the UI locale.
export function useFormat() {
  const { locale, t, te } = useI18n()
  const entity = useEntityStore()

  const intlLocale = computed(() => (locale.value === 'tr' ? 'tr-TR' : 'en-GB'))
  const currency = computed(() => entity.entities.find((e) => e.id === entity.currentEntityId)?.currency ?? 'TRY')

  function money(value: number, compact = false): string {
    return new Intl.NumberFormat(intlLocale.value, {
      style: 'currency',
      currency: currency.value,
      currencyDisplay: 'narrowSymbol',
      notation: compact ? 'compact' : 'standard',
      maximumFractionDigits: compact ? 1 : 2,
    }).format(value)
  }

  function number(value: number, compact = false): string {
    return new Intl.NumberFormat(intlLocale.value, {
      notation: compact ? 'compact' : 'standard',
      maximumFractionDigits: compact ? 1 : 2,
    }).format(value)
  }

  function value(raw: number, format: ValueFormat, compact = false): string {
    return format === 'money' ? money(raw, compact) : number(raw, compact)
  }

  function percent(raw: number): string {
    return new Intl.NumberFormat(intlLocale.value, { maximumFractionDigits: 1, signDisplay: 'always' }).format(raw) + '%'
  }

  // Dates arrive as YYYY-MM-DD: parsed as local calendar dates, never
  // through `new Date(string)`, which would read them as UTC midnight and
  // can print the previous day.
  function parseDate(iso: string): Date {
    const [year, month, day] = iso.split('-').map(Number)
    return new Date(year, month - 1, day ?? 1)
  }

  function date(iso: string): string {
    return new Intl.DateTimeFormat(intlLocale.value, { day: 'numeric', month: 'short', year: 'numeric' }).format(parseDate(iso))
  }

  function shortDate(iso: string): string {
    return new Intl.DateTimeFormat(intlLocale.value, { day: 'numeric', month: 'short' }).format(parseDate(iso))
  }

  function month(yearMonth: string): string {
    const parsed = parseDate(`${yearMonth}-01`)
    // The year only where it changes the reading: on January.
    const options: Intl.DateTimeFormatOptions = parsed.getMonth() === 0 ? { month: 'short', year: '2-digit' } : { month: 'short' }
    return new Intl.DateTimeFormat(intlLocale.value, options).format(parsed)
  }

  function dateTime(iso: string): string {
    return new Intl.DateTimeFormat(intlLocale.value, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
  }

  // Translates a backend key under `prefix`, falling back to the raw value
  // -- a status the locale file doesn't know yet still shows as itself.
  function keyed(prefix: string, key: string): string {
    const path = `${prefix}.${key}`
    return te(path) ? t(path) : key
  }

  return { money, number, value, percent, date, shortDate, month, dateTime, keyed }
}
