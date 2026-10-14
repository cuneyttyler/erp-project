import { useI18n } from 'vue-i18n'

// Human names for catalog codes. The backend sends keys
// (`purchase_order.approve`); what they're called is a UI concern, so it
// lives in the locale files: one entry per resource and one per operation,
// combined here -- not one per action, which would be ~150 strings that say
// the same few verbs over and over. An unknown key shows as itself, so a
// resource added on the backend is visible (if unpolished) before anyone
// has named it.
export function useActionLabels() {
  const { t, te } = useI18n()

  function keyed(prefix: string, key: string): string {
    const path = `${prefix}.${key}`
    return te(path) ? t(path) : key.replace(/_/g, ' ')
  }

  const resource = (key: string) => keyed('access.resources', key)
  const operation = (name: string) => keyed('access.operations', name)

  function group(key: string): string {
    const path = `plugins.catalog.${key}.name`
    return te(path) ? t(path) : keyed('access.groups', key)
  }

  // "Invoices: Send"
  function action(code: string): string {
    const [resourceKey, operationName] = code.split('.')
    return operationName ? `${resource(resourceKey)}: ${operation(operationName)}` : keyed('access.resources', code)
  }

  // Built-in roles/permissions are named in English by the backend; show
  // the localized name for those, the admin's own name for the rest.
  function systemName(record: { name: string; system_key: string | null }): string {
    if (!record.system_key) return record.name
    const [kind, pluginKey, level] = record.system_key.split(':')
    if (kind === 'plugin' && level) return `${group(pluginKey)}: ${t(`access.levels.${level}`)}`
    return keyed('access.systemRoles', record.system_key)
  }

  return { resource, operation, group, action, systemName }
}
