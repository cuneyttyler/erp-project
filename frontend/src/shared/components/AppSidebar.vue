<script setup lang="ts">
import {
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  ChevronDownIcon,
  ClipboardDocumentCheckIcon,
  HomeIcon,
  PuzzlePieceIcon,
  SparklesIcon,
  UserCircleIcon,
} from '@heroicons/vue/24/outline'
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { navGroups, plugins } from '@/plugins/registry'
import AppLogo from '@/shared/components/AppLogo.vue'
import type { PluginPage } from '@/plugins/types'
import { useAuthStore } from '@/shared/stores/auth'
import { usePluginStore } from '@/shared/stores/plugins'

// Collapsible left nav (replaces the old header-row nav). Collapse state
// persists across sessions since re-collapsing on every reload would be
// annoying for anyone who deliberately narrowed it for screen space.
const COLLAPSE_KEY = 'sidebar-collapsed'
const collapsed = ref(localStorage.getItem(COLLAPSE_KEY) === 'true')

function toggle() {
  collapsed.value = !collapsed.value
  localStorage.setItem(COLLAPSE_KEY, String(collapsed.value))
}

const pluginStore = usePluginStore()
const auth = useAuthStore()
const { t } = useI18n()

// The system screens, which no plugin provides and nobody can remove. The
// panel and the assistant sit at the top, outside any group -- the two
// things every user wants one click away; the audit log and the
// administration pages sit at the bottom. Everything in between comes from
// an installed plugin's manifest, so removing a plugin removes its links
// (and an emptied group disappears with them).
const topItems = [
  { to: '/panel', labelKey: 'nav.dashboard', icon: HomeIcon },
  { to: '/assistant', labelKey: 'nav.assistant', icon: SparklesIcon },
]
const bottomItems = computed(() => [
  { to: '/audit-log', labelKey: 'nav.auditLog', icon: ClipboardDocumentCheckIcon },
  ...(auth.isOrgAdmin ? [{ to: '/users', labelKey: 'nav.users', icon: UserCircleIcon }] : []),
  { to: '/plugins', labelKey: 'nav.plugins', icon: PuzzlePieceIcon },
])

// REQ-CORE-UX-005 (docs/feedback.md "Feedback 1": "Sol panel çok kalabalık,
// öğeleri gruplayalım") -- related screens live under a collapsible section
// instead of one flat list that grows with every plugin a tenant installs.
// A page is offered when its plugin is installed and the user holds the
// page's action.
const visibleGroups = computed(() =>
  navGroups
    .map((group) => ({
      ...group,
      items: plugins
        .filter((plugin) => plugin.navGroup === group.id && pluginStore.isActive(plugin.key))
        .flatMap((plugin): PluginPage[] => plugin.pages)
        .filter((page) => auth.can(page.action)),
    }))
    .filter((group) => group.items.length > 0),
)

const GROUP_STATE_KEY = 'sidebar-group-collapsed'
const storedGroupState = JSON.parse(localStorage.getItem(GROUP_STATE_KEY) ?? '{}')
const groupCollapsed = reactive<Record<string, boolean>>(
  Object.fromEntries(navGroups.map((g) => [g.id, storedGroupState[g.id] ?? false])),
)

function toggleGroup(id: string) {
  groupCollapsed[id] = !groupCollapsed[id]
  localStorage.setItem(GROUP_STATE_KEY, JSON.stringify(groupCollapsed))
}

const linkClass =
  'mx-2 flex items-center gap-3 rounded px-2 py-2 text-sm text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-800 dark:hover:text-neutral-100'
const activeLinkClass = '!bg-blue-50 !text-blue-700 dark:!bg-blue-950 dark:!text-blue-300'
</script>

<template>
  <aside
    class="flex h-full flex-col border-r border-neutral-200 bg-white transition-[width] duration-150 dark:border-neutral-800 dark:bg-neutral-900"
    :class="collapsed ? 'w-14' : 'w-56'"
  >
    <div class="flex items-center justify-between border-b border-neutral-200 px-3 py-3 dark:border-neutral-800">
      <AppLogo v-if="!collapsed" />
      <button
        class="ml-auto rounded p-1 text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 dark:hover:bg-neutral-800 dark:hover:text-neutral-100"
        :aria-label="collapsed ? 'Expand menu' : 'Collapse menu'"
        @click="toggle"
      >
        <ChevronDoubleRightIcon v-if="collapsed" class="h-4 w-4" />
        <ChevronDoubleLeftIcon v-else class="h-4 w-4" />
      </button>
    </div>

    <nav class="flex-1 space-y-1 overflow-y-auto py-2">
      <!-- exact-active: "/" would otherwise count as active on every page -->
      <RouterLink
        v-for="item in topItems"
        :key="item.to"
        :to="item.to"
        :class="linkClass"
        :exact-active-class="activeLinkClass"
        active-class=""
        :title="collapsed ? t(item.labelKey) : undefined"
      >
        <component :is="item.icon" class="h-5 w-5 shrink-0" />
        <span v-if="!collapsed" class="truncate">{{ t(item.labelKey) }}</span>
      </RouterLink>

      <div v-for="group in visibleGroups" :key="group.id">
        <button
          v-if="!collapsed"
          class="mx-2 mt-2 flex w-[calc(100%-1rem)] items-center justify-between px-2 py-1 text-xs font-semibold uppercase tracking-wide text-neutral-400 hover:text-neutral-600 dark:text-neutral-500 dark:hover:text-neutral-300"
          @click="toggleGroup(group.id)"
        >
          <span>{{ t(group.labelKey) }}</span>
          <ChevronDownIcon class="h-3.5 w-3.5 transition-transform" :class="groupCollapsed[group.id] ? '-rotate-90' : ''" />
        </button>
        <div v-show="collapsed || !groupCollapsed[group.id]" class="space-y-0.5">
          <RouterLink
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            :class="linkClass"
            :active-class="activeLinkClass"
            :title="collapsed ? t(item.labelKey) : undefined"
          >
            <component :is="item.icon" class="h-5 w-5 shrink-0" />
            <span v-if="!collapsed" class="truncate">{{ t(item.labelKey) }}</span>
          </RouterLink>
        </div>
      </div>
    </nav>

    <div class="space-y-0.5 border-t border-neutral-200 py-2 dark:border-neutral-800">
      <RouterLink
        v-for="item in bottomItems"
        :key="item.to"
        :to="item.to"
        :class="linkClass"
        :active-class="activeLinkClass"
        :title="collapsed ? t(item.labelKey) : undefined"
      >
        <component :is="item.icon" class="h-5 w-5 shrink-0" />
        <span v-if="!collapsed" class="truncate">{{ t(item.labelKey) }}</span>
      </RouterLink>
    </div>
  </aside>
</template>
