<script setup lang="ts">
import {
  ArrowDownIcon,
  ArrowUpIcon,
  Bars3Icon,
  BellAlertIcon,
  BoltIcon,
  ChartBarIcon,
  HashtagIcon,
  LockClosedIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  TableCellsIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { plugins as manifests } from '@/plugins/registry'
import { usePluginStore, type WidgetKind, type WidgetSize, type WidgetState } from '@/shared/stores/plugins'

// Plugin management: which plugins this tenant has installed (tenant-wide,
// admins only) and which widgets are on this user's home panel (per user).
// Both live here because they're the same act -- deciding what the app
// shows -- and a widget only exists while its plugin is installed.
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = usePluginStore()

type Tab = 'plugins' | 'widgets'
const tab = computed<Tab>(() => (route.query.tab === 'widgets' ? 'widgets' : 'plugins'))
function setTab(next: Tab) {
  router.replace({ query: next === 'widgets' ? { tab: 'widgets' } : {} })
}

const error = ref('')
function reportError(e: any, fallbackKey: string) {
  error.value = e?.response?.data?.detail ?? t(fallbackKey)
}

// ---------------------------------------------------------------- plugins
type PluginFilter = 'all' | 'installed' | 'available'
const pluginFilter = ref<PluginFilter>('all')
const pluginSearch = ref('')
const busyPlugin = ref<string | null>(null)

const pluginCards = computed(() =>
  manifests.map((manifest) => {
    const state = store.stateByKey[manifest.key]
    return {
      manifest,
      name: t(`plugins.catalog.${manifest.key}.name`),
      description: t(`plugins.catalog.${manifest.key}.description`),
      isLicensed: state?.is_licensed ?? false,
      isActive: state?.is_active ?? false,
      widgetCount: state?.widget_count ?? 0,
    }
  }),
)

const filteredPlugins = computed(() => {
  const query = pluginSearch.value.trim().toLocaleLowerCase()
  return pluginCards.value.filter((card) => {
    if (pluginFilter.value === 'installed' && !card.isActive) return false
    if (pluginFilter.value === 'available' && card.isActive) return false
    return !query || `${card.name} ${card.description}`.toLocaleLowerCase().includes(query)
  })
})

const pluginSections = computed(() =>
  [
    { id: 'core', titleKey: 'plugins.sections.core', cards: filteredPlugins.value.filter((card) => !card.manifest.package) },
    { id: 'packages', titleKey: 'plugins.sections.packages', cards: filteredPlugins.value.filter((card) => card.manifest.package) },
  ].filter((section) => section.cards.length > 0),
)

const installedCount = computed(() => pluginCards.value.filter((card) => card.isActive).length)

async function togglePlugin(key: string, isEnabled: boolean) {
  error.value = ''
  busyPlugin.value = key
  try {
    await store.setPluginEnabled(key, isEnabled)
  } catch (e) {
    reportError(e, 'plugins.errors.toggle')
  } finally {
    busyPlugin.value = null
  }
}

// ---------------------------------------------------------------- widgets
const KIND_ICON: Record<WidgetKind, typeof ChartBarIcon> = {
  stat: HashtagIcon,
  chart: ChartBarIcon,
  table: TableCellsIcon,
  attention: BellAlertIcon,
  quick_actions: BoltIcon,
}
const SIZES: WidgetSize[] = ['sm', 'md', 'lg']

const widgetSearch = ref('')
const isSaving = ref(false)

function isOnPanel(widget: WidgetState) {
  return widget.is_enabled && widget.is_available
}
const onPanel = computed(() => store.widgets.filter(isOnPanel))
const offPanel = computed(() => store.widgets.filter((widget) => !isOnPanel(widget)))

function pluginName(key: string | null) {
  return key ? t(`plugins.catalog.${key}.name`) : t('plugins.system')
}

// Everything not on the panel, grouped under the plugin that provides it:
// system widgets first, then in the plugin catalog's own order.
const availableGroups = computed(() => {
  const query = widgetSearch.value.trim().toLocaleLowerCase()
  const matches = offPanel.value.filter((widget) => {
    if (!query) return true
    const text = `${t(`widgets.catalog.${widget.key}.title`)} ${t(`widgets.catalog.${widget.key}.description`)}`
    return text.toLocaleLowerCase().includes(query)
  })
  const keys: (string | null)[] = [null, ...manifests.map((manifest) => manifest.key)]
  return keys
    .map((key) => {
      const widgets = matches.filter((widget) => widget.plugin === key)
      const state = key ? store.stateByKey[key] : undefined
      return {
        key,
        name: pluginName(key),
        widgets,
        isAvailable: widgets.some((widget) => widget.is_available),
        isLicensed: key ? (state?.is_licensed ?? false) : true,
      }
    })
    .filter((group) => group.widgets.length > 0)
})

// The saved list is the panel's order: what's on the panel first, in the
// order shown here, then everything else untouched.
async function commit(panel: WidgetState[], rest: WidgetState[]) {
  error.value = ''
  isSaving.value = true
  try {
    await store.saveLayout([...panel, ...rest])
  } catch (e) {
    reportError(e, 'plugins.errors.layout')
  } finally {
    isSaving.value = false
  }
}

function addWidget(widget: WidgetState) {
  commit(
    [...onPanel.value, { ...widget, is_enabled: true }],
    offPanel.value.filter((other) => other.key !== widget.key),
  )
}

function removeWidget(widget: WidgetState) {
  commit(
    onPanel.value.filter((other) => other.key !== widget.key),
    [{ ...widget, is_enabled: false }, ...offPanel.value],
  )
}

function setSize(widget: WidgetState, size: WidgetSize) {
  if (widget.size === size) return
  commit(
    onPanel.value.map((other) => (other.key === widget.key ? { ...other, size } : other)),
    offPanel.value,
  )
}

function moveTo(fromIndex: number, toIndex: number) {
  if (toIndex < 0 || toIndex >= onPanel.value.length || fromIndex === toIndex) return
  const panel = [...onPanel.value]
  panel.splice(toIndex, 0, panel.splice(fromIndex, 1)[0])
  commit(panel, offPanel.value)
}

// Native HTML5 drag-and-drop for reordering, with the up/down buttons as
// the keyboard path to the same result.
const draggingIndex = ref<number | null>(null)
const dropIndex = ref<number | null>(null)

function onDrop(targetIndex: number) {
  if (draggingIndex.value !== null) moveTo(draggingIndex.value, targetIndex)
  draggingIndex.value = null
  dropIndex.value = null
}

async function resetLayout() {
  error.value = ''
  isSaving.value = true
  try {
    await store.resetLayout()
  } catch (e) {
    reportError(e, 'plugins.errors.layout')
  } finally {
    isSaving.value = false
  }
}

const inputClass = 'rounded border border-neutral-300 bg-white py-1.5 pl-8 pr-2 text-sm dark:border-neutral-700 dark:bg-neutral-900'
const secondaryButton =
  'rounded border border-neutral-300 bg-white px-3 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:bg-neutral-800'
const iconButton =
  'rounded p-1 text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent dark:hover:bg-neutral-800 dark:hover:text-neutral-100'
</script>

<template>
  <section class="p-6 lg:p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('plugins.title') }}</h1>
    <p class="mt-1 max-w-3xl text-sm text-neutral-500">{{ t('plugins.subtitle') }}</p>

    <div class="mt-5 flex gap-1 border-b border-neutral-200 dark:border-neutral-800" role="tablist">
      <button
        v-for="option in ['plugins', 'widgets'] as Tab[]"
        :key="option"
        role="tab"
        :aria-selected="tab === option"
        class="-mb-px border-b-2 px-3 py-2 text-sm font-medium"
        :class="
          tab === option
            ? 'border-blue-600 text-blue-700 dark:text-blue-400'
            : 'border-transparent text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200'
        "
        @click="setTab(option)"
      >
        {{ t(`plugins.tabs.${option}`) }}
        <span class="ml-1 text-xs font-normal text-neutral-400">
          {{ option === 'plugins' ? `${installedCount}/${pluginCards.length}` : onPanel.length }}
        </span>
      </button>
    </div>

    <p v-if="error" class="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300" role="alert">
      {{ error }}
    </p>

    <!-- ============================================================ Plugins -->
    <div v-if="tab === 'plugins'">
      <p
        v-if="!store.canManage"
        class="mt-4 flex items-center gap-2 rounded border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-600 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-400"
      >
        <LockClosedIcon class="h-4 w-4 shrink-0" />
        {{ t('plugins.readOnly') }}
      </p>

      <div class="mt-4 flex flex-wrap items-center gap-3">
        <div class="relative">
          <MagnifyingGlassIcon class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" />
          <input v-model="pluginSearch" type="search" :placeholder="t('plugins.search')" :aria-label="t('plugins.search')" :class="[inputClass, 'w-64']" />
        </div>
        <div class="flex rounded border border-neutral-300 bg-white p-0.5 text-sm dark:border-neutral-700 dark:bg-neutral-900">
          <button
            v-for="option in ['all', 'installed', 'available'] as PluginFilter[]"
            :key="option"
            class="rounded px-2.5 py-1"
            :class="pluginFilter === option ? 'bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900' : 'text-neutral-600 dark:text-neutral-400'"
            :aria-pressed="pluginFilter === option"
            @click="pluginFilter = option"
          >
            {{ t(`plugins.filters.${option}`) }}
          </button>
        </div>
      </div>

      <p v-if="pluginSections.length === 0" class="mt-10 text-center text-sm text-neutral-500">{{ t('plugins.noMatches') }}</p>

      <div v-for="section in pluginSections" :key="section.id" class="mt-6">
        <h2 class="text-xs font-semibold uppercase tracking-wide text-neutral-500">{{ t(section.titleKey) }}</h2>
        <div class="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
          <article
            v-for="card in section.cards"
            :key="card.manifest.key"
            class="flex flex-col rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900"
          >
            <div class="flex items-start gap-3">
              <span
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                :class="card.isActive ? 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300' : 'bg-neutral-100 text-neutral-500 dark:bg-neutral-800'"
              >
                <component :is="card.manifest.icon" class="h-5 w-5" />
              </span>
              <div class="min-w-0 flex-1">
                <h3 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">{{ card.name }}</h3>
                <p class="mt-0.5 flex items-center gap-1.5 text-xs">
                  <template v-if="card.isActive">
                    <span class="h-1.5 w-1.5 rounded-full bg-green-600" />
                    <span class="text-neutral-600 dark:text-neutral-400">{{ t('plugins.status.installed') }}</span>
                  </template>
                  <template v-else-if="!card.isLicensed">
                    <LockClosedIcon class="h-3.5 w-3.5 text-neutral-400" />
                    <span class="text-neutral-500">{{ t('plugins.status.notLicensed') }}</span>
                  </template>
                  <span v-else class="text-neutral-500">{{ t('plugins.status.notInstalled') }}</span>
                </p>
              </div>
            </div>

            <p class="mt-3 text-sm text-neutral-600 dark:text-neutral-400">{{ card.description }}</p>

            <div class="mt-3 flex flex-wrap gap-1.5">
              <span
                v-for="page in card.manifest.pages"
                :key="page.path"
                class="flex items-center gap-1 rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300"
              >
                <component :is="page.icon" class="h-3.5 w-3.5" />
                {{ t(page.labelKey) }}
              </span>
            </div>

            <div class="mt-auto flex items-center justify-between gap-3 pt-4">
              <span class="text-xs text-neutral-500">{{ t('plugins.widgetCount', { count: card.widgetCount }, card.widgetCount) }}</span>
              <button
                v-if="card.isActive"
                :class="secondaryButton"
                :disabled="!store.canManage || busyPlugin === card.manifest.key"
                @click="togglePlugin(card.manifest.key, false)"
              >
                {{ t('plugins.actions.remove') }}
              </button>
              <button
                v-else
                class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="!store.canManage || !card.isLicensed || busyPlugin === card.manifest.key"
                @click="togglePlugin(card.manifest.key, true)"
              >
                {{ t('plugins.actions.add') }}
              </button>
            </div>
          </article>
        </div>
      </div>

      <p class="mt-6 max-w-3xl text-xs text-neutral-500">{{ t('plugins.removeNote') }}</p>
    </div>

    <!-- ====================================================== Panel widgets -->
    <div v-else>
      <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p class="max-w-2xl text-sm text-neutral-600 dark:text-neutral-400">{{ t('plugins.widgets.intro') }}</p>
        <div class="flex items-center gap-3">
          <span class="text-xs text-neutral-500" aria-live="polite">{{ isSaving ? t('plugins.widgets.saving') : t('plugins.widgets.saved') }}</span>
          <button :class="secondaryButton" :disabled="isSaving" @click="resetLayout">{{ t('plugins.widgets.reset') }}</button>
          <RouterLink :to="{ name: 'dashboard' }" class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">
            {{ t('plugins.widgets.viewPanel') }}
          </RouterLink>
        </div>
      </div>

      <h2 class="mt-6 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        {{ t('plugins.widgets.onPanel') }} <span class="font-normal">({{ onPanel.length }})</span>
      </h2>
      <p v-if="onPanel.length === 0" class="mt-3 rounded-lg border border-dashed border-neutral-300 p-6 text-center text-sm text-neutral-500 dark:border-neutral-700">
        {{ t('plugins.widgets.panelEmpty') }}
      </p>
      <ol v-else class="mt-3 divide-y divide-neutral-100 rounded-lg border border-neutral-200 bg-white dark:divide-neutral-800 dark:border-neutral-800 dark:bg-neutral-900">
        <li
          v-for="(widget, index) in onPanel"
          :key="widget.key"
          draggable="true"
          class="flex items-center gap-3 px-3 py-2.5"
          :class="[
            draggingIndex === index ? 'opacity-40' : '',
            dropIndex === index && draggingIndex !== index ? 'bg-blue-50 dark:bg-blue-950/50' : '',
          ]"
          @dragstart="draggingIndex = index"
          @dragend="((draggingIndex = null), (dropIndex = null))"
          @dragover.prevent="dropIndex = index"
          @drop.prevent="onDrop(index)"
        >
          <Bars3Icon class="h-4 w-4 shrink-0 cursor-grab text-neutral-400" aria-hidden="true" />
          <component :is="KIND_ICON[widget.kind]" class="h-5 w-5 shrink-0 text-neutral-500" />
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-neutral-900 dark:text-neutral-100">{{ t(`widgets.catalog.${widget.key}.title`) }}</p>
            <p class="truncate text-xs text-neutral-500">{{ pluginName(widget.plugin) }} · {{ t(`widgets.catalog.${widget.key}.description`) }}</p>
          </div>

          <div class="flex shrink-0 rounded border border-neutral-300 p-0.5 text-xs dark:border-neutral-700" role="group" :aria-label="t('plugins.widgets.size')">
            <button
              v-for="size in SIZES"
              :key="size"
              class="rounded px-2 py-0.5"
              :class="widget.size === size ? 'bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900' : 'text-neutral-600 dark:text-neutral-400'"
              :aria-pressed="widget.size === size"
              :title="t(`plugins.widgets.sizes.${size}`)"
              @click="setSize(widget, size)"
            >
              {{ t(`plugins.widgets.sizeShort.${size}`) }}
            </button>
          </div>

          <div class="flex shrink-0 items-center">
            <button :class="iconButton" :disabled="index === 0" :aria-label="t('plugins.widgets.moveUp')" :title="t('plugins.widgets.moveUp')" @click="moveTo(index, index - 1)">
              <ArrowUpIcon class="h-4 w-4" />
            </button>
            <button
              :class="iconButton"
              :disabled="index === onPanel.length - 1"
              :aria-label="t('plugins.widgets.moveDown')"
              :title="t('plugins.widgets.moveDown')"
              @click="moveTo(index, index + 1)"
            >
              <ArrowDownIcon class="h-4 w-4" />
            </button>
            <button :class="iconButton" :aria-label="t('plugins.widgets.remove')" :title="t('plugins.widgets.remove')" @click="removeWidget(widget)">
              <XMarkIcon class="h-4 w-4" />
            </button>
          </div>
        </li>
      </ol>

      <div class="mt-8 flex flex-wrap items-center justify-between gap-3">
        <h2 class="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          {{ t('plugins.widgets.available') }} <span class="font-normal">({{ offPanel.length }})</span>
        </h2>
        <div class="relative">
          <MagnifyingGlassIcon class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" />
          <input
            v-model="widgetSearch"
            type="search"
            :placeholder="t('plugins.widgets.search')"
            :aria-label="t('plugins.widgets.search')"
            :class="[inputClass, 'w-64']"
          />
        </div>
      </div>

      <p v-if="availableGroups.length === 0" class="mt-6 text-center text-sm text-neutral-500">
        {{ offPanel.length === 0 ? t('plugins.widgets.allAdded') : t('plugins.noMatches') }}
      </p>

      <div v-for="group in availableGroups" :key="group.key ?? 'system'" class="mt-5">
        <h3 class="flex items-center gap-2 text-sm font-medium text-neutral-800 dark:text-neutral-200">
          {{ group.name }}
          <span v-if="!group.isAvailable" class="flex items-center gap-1 text-xs font-normal text-neutral-500">
            <LockClosedIcon class="h-3.5 w-3.5" />
            {{ group.isLicensed ? t('plugins.widgets.pluginRemoved') : t('plugins.status.notLicensed') }}
          </span>
        </h3>
        <div class="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2 2xl:grid-cols-3">
          <div
            v-for="widget in group.widgets"
            :key="widget.key"
            class="flex items-start gap-3 rounded-lg border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900"
            :class="widget.is_available ? '' : 'opacity-60'"
          >
            <component :is="KIND_ICON[widget.kind]" class="mt-0.5 h-5 w-5 shrink-0 text-neutral-500" />
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium text-neutral-900 dark:text-neutral-100">{{ t(`widgets.catalog.${widget.key}.title`) }}</p>
              <p class="mt-0.5 text-xs text-neutral-500">{{ t(`widgets.catalog.${widget.key}.description`) }}</p>
            </div>
            <button
              class="flex shrink-0 items-center gap-1 rounded border border-neutral-300 px-2 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
              :disabled="!widget.is_available"
              @click="addWidget(widget)"
            >
              <PlusIcon class="h-3.5 w-3.5" />
              {{ t('plugins.actions.add') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
