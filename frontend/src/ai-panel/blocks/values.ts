import { useI18n } from 'vue-i18n'

import { useFormat } from '@/core/dashboard/format'

// How a raw API value reads to a person. The assistant's tables and cards
// show whatever fields a resource has, so there's no per-column
// configuration to lean on -- the value's own shape decides: an ISO date
// prints as a date, a decimal string as an amount, a known status in the
// user's language. Anything unrecognized prints as itself.
const MONEY_HINTS = ['total', 'amount', 'balance', 'price', 'salary', 'cost', 'premium', 'tax', 'debit', 'credit', 'cash', 'paid', 'due', 'value']
const KEYED_FIELDS = ['status', 'type', 'channel', 'method', 'platform', 'direction']

export function useValues() {
  const { t, te } = useI18n()
  const format = useFormat()

  // A field's name as a column or row header: a translation where the
  // panel widgets already have one, otherwise the field name tidied up.
  function label(field: string): string {
    const key = field.split('.').pop() ?? field
    if (te(`widgets.columns.${key}`)) return t(`widgets.columns.${key}`)
    const words = key.replace(/_/g, ' ')
    return words.charAt(0).toUpperCase() + words.slice(1)
  }

  function isMoney(field: string): boolean {
    const key = field.toLowerCase()
    return MONEY_HINTS.some((hint) => key.includes(hint)) && !key.endsWith('_id') && !key.includes('tax_id')
  }

  // An amount or quantity (right-aligned in a table). Plain integers are
  // mostly ids and stay left-aligned with the text they identify.
  function isNumeric(value: unknown): boolean {
    return typeof value === 'string' && /^-?\d+\.\d+$/.test(value)
  }

  function text(field: string, value: unknown): string {
    if (value === null || value === undefined || value === '') return '—'
    if (typeof value === 'boolean') return value ? t('assistant.values.yes') : t('assistant.values.no')
    if (Array.isArray(value)) return t('assistant.values.items', { count: value.length }, value.length)
    if (typeof value === 'object') return JSON.stringify(value)
    if (typeof value === 'string') {
      if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return format.date(value)
      if (/^\d{4}-\d{2}-\d{2}T/.test(value)) return format.dateTime(value)
      // A decimal string is an amount or a quantity; a string of digits
      // alone is a code (an account "100", a tax id) and stays as typed.
      if (/^-?\d+\.\d+$/.test(value)) return isMoney(field) ? format.money(Number(value)) : format.number(Number(value))
      const key = field.split('.').pop() ?? field
      if (KEYED_FIELDS.some((suffix) => key === suffix || key.endsWith(`_${suffix}`))) return format.keyed('widgets.status', value)
      return value
    }
    return String(value)
  }

  return { label, text, isMoney, isNumeric }
}
