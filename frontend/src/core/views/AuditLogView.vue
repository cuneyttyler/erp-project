<script setup lang="ts">
import { ArrowUturnLeftIcon, ChevronRightIcon, SparklesIcon, UserIcon } from '@heroicons/vue/24/outline'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useActionLabels } from '@/core/access/labels'
import PageInsights from '@/core/dashboard/PageInsights.vue'
import { apiErrorMessage, useAccessStore } from '@/core/stores/access'
import { apiClient } from '@/shared/api/client'
import AppModal from '@/shared/components/AppModal.vue'
import { useAuthStore } from '@/shared/stores/auth'

// The audit log (REQ-CORE-AUDIT-001/004): every action taken, by whom,
// through which channel (a screen, or the AI assistant on their behalf),
// and what it changed. An admin sees everything; anyone else sees their own
// actions plus actions on things they're allowed to view -- the backend
// decides, this page just shows what it's given.
//
// An entry can be reverted from here. Reverting never edits the log: it
// performs the inverse action, which appears as a new entry.

interface Change {
  field: string
  before: unknown
  after: unknown
}

interface AuditEntry {
  id: number
  created_at: string
  user: { id: number; username: string; full_name: string } | null
  channel: 'manual' | 'ai'
  action: string
  resource: string
  operation: string
  target_id: string
  target_label: string
  changes: Change[]
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  // The entry this one undoes, and the entry that undid this one.
  reverts: number | null
  reverted_by: number | null
  revert: { can_revert: boolean; reason: string | null }
}

const PAGE_SIZE = 50

const { t, te, locale } = useI18n()
const auth = useAuthStore()
const access = useAccessStore()
const labels = useActionLabels()

const entries = ref<AuditEntry[]>([])
const total = ref(0)
const page = ref(1)
const isLoading = ref(true)
const error = ref('')
const expanded = reactive<Record<number, boolean>>({})

const filters = reactive({ q: '', user: '', channel: '', resource: '', date_from: '', date_to: '' })

async function load() {
  isLoading.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = { page: page.value }
    for (const [key, value] of Object.entries(filters)) if (value) params[key] = value
    const { data } = await apiClient.get<{ count: number; results: AuditEntry[] }>('access/audit-log/', { params })
    entries.value = data.results
    total.value = data.count
  } catch (e) {
    error.value = apiErrorMessage(e, t('audit.errors.load'))
  } finally {
    isLoading.value = false
  }
}

// Any filter change starts again from the first page; typing in the search
// box waits for a pause rather than firing a request per keystroke.
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(
  () => ({ ...filters }),
  (next, previous) => {
    page.value = 1
    clearTimeout(searchTimer)
    if (next.q !== previous.q) searchTimer = setTimeout(load, 300)
    else load()
  },
)
watch(page, load)

onMounted(() => {
  load()
  access.fetchCatalog().catch(() => undefined)
  // Only an admin may list users (and so filter by one).
  if (auth.isOrgAdmin) access.fetchAll().catch(() => undefined)
})

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const hasFilters = computed(() => Object.values(filters).some(Boolean))
function clearFilters() {
  Object.assign(filters, { q: '', user: '', channel: '', resource: '', date_from: '', date_to: '' })
}

const resourceOptions = computed(() =>
  access.catalog.map((group) => ({
    name: labels.group(group.group),
    resources: group.resources.map((resource) => ({ key: resource.key, name: labels.resource(resource.key) })),
  })),
)

function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat(locale.value === 'tr' ? 'tr-TR' : 'en-GB', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(iso))
}

// A catalog action reads as "Invoices: Send"; the few entries that aren't
// catalog actions (an assistant conversation, a plugin being added) have
// their own names.
function actionLabel(entry: AuditEntry): string {
  const special = `audit.special.${entry.action.replace('.', '_')}`
  if (te(special)) return t(special)
  return labels.action(entry.action)
}

function targetLabel(entry: AuditEntry): string {
  if (entry.target_label) return entry.target_label
  return entry.target_id ? `#${entry.target_id}` : ''
}

function printValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// What to show when a row is opened: the fields that changed for an update
// or a transition; the whole record for a create or a delete.
function detailRows(entry: AuditEntry): Change[] {
  if (entry.before && entry.after) return entry.changes
  const snapshot = entry.after ?? entry.before ?? {}
  return Object.keys(snapshot).map((field) => ({
    field,
    before: entry.before ? entry.before[field] : undefined,
    after: entry.after ? entry.after[field] : undefined,
  }))
}

// ----------------------------------------------------------------- revert
const reverting = ref<AuditEntry | null>(null)
const revertError = ref('')
const isReverting = ref(false)

function revertEffect(entry: AuditEntry): string {
  const key = `audit.revert.effects.${entry.operation}`
  return te(key) ? t(key) : t('audit.revert.effects.other')
}

async function confirmRevert() {
  if (!reverting.value) return
  revertError.value = ''
  isReverting.value = true
  try {
    await apiClient.post(`access/audit-log/${reverting.value.id}/revert/`)
    reverting.value = null
    await load()
  } catch (e: any) {
    const reason = e?.response?.data?.reason
    const detail = e?.response?.data?.detail
    revertError.value = reason && te(`audit.reasons.${reason}`) ? `${t(`audit.reasons.${reason}`)}${detail ? ` (${detail})` : ''}` : apiErrorMessage(e, t('audit.errors.revert'))
  } finally {
    isReverting.value = false
  }
}

const inputClass = 'rounded border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900'
const th = 'px-3 py-2 text-left text-xs font-medium text-neutral-500'
const td = 'px-3 py-2.5 align-top text-sm text-neutral-800 dark:text-neutral-200'
const secondaryButton =
  'rounded border border-neutral-300 bg-white px-3 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:bg-neutral-800'
</script>

<template>
  <section class="p-6 lg:p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('audit.title') }}</h1>
    <p class="mt-1 max-w-3xl text-sm text-neutral-500">{{ auth.isOrgAdmin ? t('audit.subtitleAdmin') : t('audit.subtitleMember') }}</p>
    <PageInsights screen-key="audit-log" :widgets="['audit_activity','audit_top_users']" />

    <div class="mt-5 flex flex-wrap items-end gap-3">
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-neutral-500">{{ t('audit.filters.search') }}</span>
        <input v-model="filters.q" type="search" :placeholder="t('audit.filters.searchPlaceholder')" :class="[inputClass, 'w-56']" />
      </label>
      <label v-if="auth.isOrgAdmin" class="block">
        <span class="mb-1 block text-xs font-medium text-neutral-500">{{ t('audit.filters.user') }}</span>
        <select v-model="filters.user" :class="inputClass">
          <option value="">{{ t('audit.filters.anyone') }}</option>
          <option v-for="user in access.users" :key="user.id" :value="String(user.id)">{{ user.full_name || user.username }}</option>
        </select>
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-neutral-500">{{ t('audit.filters.channel') }}</span>
        <select v-model="filters.channel" :class="inputClass">
          <option value="">{{ t('audit.filters.anyChannel') }}</option>
          <option value="manual">{{ t('audit.channels.manual') }}</option>
          <option value="ai">{{ t('audit.channels.ai') }}</option>
        </select>
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-neutral-500">{{ t('audit.filters.resource') }}</span>
        <select v-model="filters.resource" :class="[inputClass, 'max-w-56']">
          <option value="">{{ t('audit.filters.anything') }}</option>
          <optgroup v-for="group in resourceOptions" :key="group.name" :label="group.name">
            <option v-for="resource in group.resources" :key="resource.key" :value="resource.key">{{ resource.name }}</option>
          </optgroup>
        </select>
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-neutral-500">{{ t('audit.filters.from') }}</span>
        <input v-model="filters.date_from" type="date" :class="inputClass" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-neutral-500">{{ t('audit.filters.to') }}</span>
        <input v-model="filters.date_to" type="date" :class="inputClass" />
      </label>
      <button v-if="hasFilters" class="pb-1.5 text-sm font-medium text-blue-700 hover:underline dark:text-blue-400" @click="clearFilters">{{ t('audit.filters.clear') }}</button>
    </div>

    <p v-if="error" class="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300" role="alert">{{ error }}</p>

    <div class="mt-4 overflow-x-auto rounded-lg border border-neutral-200 bg-white transition-opacity dark:border-neutral-800 dark:bg-neutral-900" :class="isLoading ? 'opacity-60' : ''">
      <table class="w-full">
        <thead class="border-b border-neutral-200 dark:border-neutral-800">
          <tr>
            <th :class="[th, 'w-8']" />
            <th :class="th">{{ t('audit.columns.when') }}</th>
            <th :class="th">{{ t('audit.columns.who') }}</th>
            <th :class="th">{{ t('audit.columns.channel') }}</th>
            <th :class="th">{{ t('audit.columns.action') }}</th>
            <th :class="th">{{ t('audit.columns.record') }}</th>
            <th :class="th" />
          </tr>
        </thead>
        <tbody>
          <template v-for="entry in entries" :key="entry.id">
            <tr class="border-b border-neutral-100 dark:border-neutral-800">
              <td :class="td">
                <button
                  class="rounded p-0.5 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-800 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
                  :aria-expanded="!!expanded[entry.id]"
                  :aria-label="t('audit.details')"
                  @click="expanded[entry.id] = !expanded[entry.id]"
                >
                  <ChevronRightIcon class="h-4 w-4 transition-transform" :class="expanded[entry.id] ? 'rotate-90' : ''" />
                </button>
              </td>
              <td :class="[td, 'whitespace-nowrap tabular-nums']">{{ formatDateTime(entry.created_at) }}</td>
              <td :class="[td, 'whitespace-nowrap']">{{ entry.user ? entry.user.full_name || entry.user.username : t('audit.system') }}</td>
              <td :class="td">
                <span
                  class="inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium"
                  :class="entry.channel === 'ai' ? 'bg-violet-50 text-violet-700 dark:bg-violet-950 dark:text-violet-300' : 'bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300'"
                >
                  <component :is="entry.channel === 'ai' ? SparklesIcon : UserIcon" class="h-3.5 w-3.5" />
                  {{ t(`audit.channels.${entry.channel}`) }}
                </span>
              </td>
              <td :class="td">
                {{ actionLabel(entry) }}
                <span v-if="entry.reverts" class="ml-1 whitespace-nowrap rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                  {{ t('audit.revertOf', { id: entry.reverts }) }}
                </span>
              </td>
              <td :class="[td, 'max-w-72 truncate']" :title="targetLabel(entry)">{{ targetLabel(entry) }}</td>
              <td :class="[td, 'whitespace-nowrap text-right']">
                <span v-if="entry.reverted_by" class="text-xs text-neutral-500">{{ t('audit.reverted', { id: entry.reverted_by }) }}</span>
                <button
                  v-else-if="entry.revert.can_revert"
                  class="inline-flex items-center gap-1 rounded border border-neutral-300 px-2 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
                  @click="((reverting = entry), (revertError = ''))"
                >
                  <ArrowUturnLeftIcon class="h-3.5 w-3.5" />{{ t('audit.revert.button') }}
                </button>
              </td>
            </tr>
            <tr v-if="expanded[entry.id]" class="border-b border-neutral-100 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-800/30">
              <td />
              <td colspan="6" class="px-3 py-3">
                <p class="text-xs text-neutral-500">
                  {{ t('audit.entryId', { id: entry.id }) }} · <span class="font-mono">{{ entry.action }}</span>
                  <template v-if="!entry.reverted_by && !entry.revert.can_revert && entry.revert.reason">
                    · {{ t(`audit.reasons.${entry.revert.reason}`) }}
                  </template>
                </p>
                <p v-if="detailRows(entry).length === 0" class="mt-2 text-sm text-neutral-500">{{ t('audit.noChanges') }}</p>
                <table v-else class="mt-2 w-full max-w-4xl text-sm">
                  <thead>
                    <tr class="text-xs text-neutral-500">
                      <th class="pb-1 pr-4 text-left font-medium">{{ t('audit.columns.field') }}</th>
                      <th v-if="entry.before" class="pb-1 pr-4 text-left font-medium">{{ t('audit.columns.before') }}</th>
                      <th v-if="entry.after" class="pb-1 text-left font-medium">{{ t('audit.columns.after') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in detailRows(entry)" :key="row.field" class="align-top">
                      <td class="py-0.5 pr-4 font-mono text-xs text-neutral-600 dark:text-neutral-400">{{ row.field }}</td>
                      <td v-if="entry.before" class="break-all py-0.5 pr-4 text-neutral-700 dark:text-neutral-300">{{ printValue(row.before) }}</td>
                      <td v-if="entry.after" class="break-all py-0.5 text-neutral-900 dark:text-neutral-100">{{ printValue(row.after) }}</td>
                    </tr>
                  </tbody>
                </table>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      <p v-if="!isLoading && entries.length === 0" class="py-10 text-center text-sm text-neutral-500">{{ hasFilters ? t('audit.noMatches') : t('audit.empty') }}</p>
    </div>

    <div v-if="total > 0" class="mt-3 flex items-center justify-between text-sm text-neutral-500">
      <span>{{ t('audit.count', { count: total }, total) }}</span>
      <div v-if="pageCount > 1" class="flex items-center gap-2">
        <button :class="secondaryButton" :disabled="page <= 1" @click="page--">{{ t('audit.previous') }}</button>
        <span>{{ t('audit.page', { page, pages: pageCount }) }}</span>
        <button :class="secondaryButton" :disabled="page >= pageCount" @click="page++">{{ t('audit.next') }}</button>
      </div>
    </div>

    <AppModal v-if="reverting" :title="t('audit.revert.title')" @close="reverting = null">
      <p class="text-sm font-medium text-neutral-900 dark:text-neutral-100">{{ actionLabel(reverting) }} · {{ targetLabel(reverting) }}</p>
      <p class="mt-2 text-sm text-neutral-700 dark:text-neutral-300">{{ revertEffect(reverting) }}</p>
      <p class="mt-2 text-xs text-neutral-500">{{ t('audit.revert.note') }}</p>
      <p v-if="revertError" class="mt-3 text-sm text-red-600 dark:text-red-400" role="alert">{{ revertError }}</p>
      <template #footer>
        <button :class="secondaryButton" @click="reverting = null">{{ t('access.actions.cancel') }}</button>
        <button class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50" :disabled="isReverting" @click="confirmRevert">
          {{ t('audit.revert.confirm') }}
        </button>
      </template>
    </AppModal>
  </section>
</template>
