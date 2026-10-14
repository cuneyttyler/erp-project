<script setup lang="ts">
import { ChevronDownIcon } from '@heroicons/vue/24/outline'
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { CatalogGroup, CatalogResource } from '@/core/stores/access'

import { useActionLabels } from './labels'

// The action catalog as a grid: one section per plugin, one row per
// resource, one checkbox per operation. Used to pick the actions of a
// permission and a user's individual actions -- and, with `readonly`, as the
// plain "everything that can be done in this app" listing.
const props = defineProps<{
  catalog: CatalogGroup[]
  modelValue: string[]
  readonly?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const { t } = useI18n()
const labels = useActionLabels()

const search = ref('')
const collapsed = reactive<Record<string, boolean>>({})
const selected = computed(() => new Set(props.modelValue))

const groups = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return props.catalog
    .map((group) => ({
      ...group,
      name: labels.group(group.group),
      resources: group.resources.filter((resource) => {
        if (!query) return true
        const text = `${labels.resource(resource.key)} ${resource.key} ${resource.operations.map((o) => labels.operation(o.name)).join(' ')}`
        return text.toLocaleLowerCase().includes(query) || labels.group(group.group).toLocaleLowerCase().includes(query)
      }),
    }))
    .filter((group) => group.resources.length > 0)
})

function codesOf(resources: CatalogResource[]): string[] {
  return resources.flatMap((resource) => resource.operations.map((operation) => operation.code))
}

function countSelected(resources: CatalogResource[]): number {
  return codesOf(resources).filter((code) => selected.value.has(code)).length
}

function setCodes(codes: string[], on: boolean) {
  const next = new Set(props.modelValue)
  for (const code of codes) {
    if (on) next.add(code)
    else next.delete(code)
  }
  emit('update:modelValue', [...next].sort())
}

function toggleAll(resources: CatalogResource[]) {
  const codes = codesOf(resources)
  setCodes(codes, countSelected(resources) < codes.length)
}
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-2">
      <input
        v-model="search"
        type="search"
        :placeholder="t('access.picker.search')"
        :aria-label="t('access.picker.search')"
        class="w-64 rounded border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
      />
      <span v-if="!readonly" class="text-xs text-neutral-500">{{ t('access.picker.selected', { count: modelValue.length }) }}</span>
    </div>

    <p v-if="groups.length === 0" class="mt-6 text-center text-sm text-neutral-500">{{ t('access.picker.noMatches') }}</p>

    <section v-for="group in groups" :key="group.group" class="mt-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
      <header class="flex items-center justify-between gap-3 bg-neutral-50 px-3 py-2 dark:bg-neutral-800/50">
        <button class="flex items-center gap-2 text-sm font-semibold text-neutral-900 dark:text-neutral-100" @click="collapsed[group.group] = !collapsed[group.group]">
          <ChevronDownIcon class="h-4 w-4 transition-transform" :class="collapsed[group.group] ? '-rotate-90' : ''" />
          {{ group.name }}
          <span v-if="!readonly" class="text-xs font-normal text-neutral-500">{{ countSelected(group.resources) }}/{{ codesOf(group.resources).length }}</span>
        </button>
        <button v-if="!readonly" class="text-xs font-medium text-blue-700 hover:underline dark:text-blue-400" @click="toggleAll(group.resources)">
          {{ countSelected(group.resources) === codesOf(group.resources).length ? t('access.picker.clearAll') : t('access.picker.selectAll') }}
        </button>
      </header>

      <ul v-show="!collapsed[group.group]" class="divide-y divide-neutral-100 dark:divide-neutral-800">
        <li v-for="resource in group.resources" :key="resource.key" class="grid grid-cols-1 gap-x-4 gap-y-1.5 px-3 py-2.5 md:grid-cols-[14rem_1fr]">
          <div>
            <button
              v-if="!readonly"
              class="text-left text-sm font-medium text-neutral-800 hover:text-blue-700 dark:text-neutral-200 dark:hover:text-blue-400"
              :title="t('access.picker.toggleRow')"
              @click="toggleAll([resource])"
            >
              {{ labels.resource(resource.key) }}
            </button>
            <span v-else class="text-sm font-medium text-neutral-800 dark:text-neutral-200">{{ labels.resource(resource.key) }}</span>
          </div>
          <div class="flex flex-wrap gap-x-4 gap-y-1.5">
            <template v-for="operation in resource.operations" :key="operation.code">
              <label v-if="!readonly" class="flex cursor-pointer items-center gap-1.5 text-sm text-neutral-700 dark:text-neutral-300">
                <input type="checkbox" class="h-4 w-4 rounded border-neutral-300" :checked="selected.has(operation.code)" @change="setCodes([operation.code], ($event.target as HTMLInputElement).checked)" />
                {{ labels.operation(operation.name) }}
              </label>
              <span
                v-else
                class="rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300"
                :title="operation.code"
              >
                {{ labels.operation(operation.name) }}
              </span>
            </template>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>
