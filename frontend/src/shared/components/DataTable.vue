<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { apiClient } from '@/shared/api/client'

// REQ-CORE-UX-001/002/003/004: a generic, reusable data-table component
// covering every "Excel-like" behavior requested in docs/feedback.md
// (Feedback 1) -- column reorder/hide/resize, per-column sort/filter,
// inline cell editing, and personal/shared saved "variants" per screen.
// Screens adopt this instead of hand-rolling a <table>; see
// ItemsView.vue/InvoicesView.vue for the reference integration.

export interface ColumnDef {
  key: string
  label: string
  sortable?: boolean
  filterable?: boolean
  editable?: boolean
  type?: 'text' | 'number' | 'boolean' | 'select'
  options?: { value: string | number | boolean; label: string }[]
  width?: number
  formatter?: (row: Record<string, any>) => string
}

const props = defineProps<{
  screenKey: string
  columns: ColumnDef[]
  rows: Record<string, any>[]
  rowKey?: string
}>()

const emit = defineEmits<{
  (e: 'cell-edit', payload: { row: Record<string, any>; column: string; value: any }): void
}>()

const rowKeyField = props.rowKey ?? 'id'

// --- Column order / visibility / width -----------------------------------
const columnOrder = ref<string[]>(props.columns.map((c) => c.key))
const hiddenColumns = ref<Set<string>>(new Set())
const columnWidths = reactive<Record<string, number>>(
  Object.fromEntries(props.columns.map((c) => [c.key, c.width ?? 160])),
)

const columnsByKey = computed(() => Object.fromEntries(props.columns.map((c) => [c.key, c])))
const visibleColumns = computed(() =>
  columnOrder.value.filter((k) => !hiddenColumns.value.has(k)).map((k) => columnsByKey.value[k]).filter(Boolean),
)

// --- Sort / filter ---------------------------------------------------------
const sort = ref<{ key: string; direction: 'asc' | 'desc' } | null>(null)
const filters = reactive<Record<string, string>>({})

function cellText(row: Record<string, any>, col: ColumnDef): string {
  if (col.formatter) return col.formatter(row)
  const value = row[col.key]
  if (value === null || value === undefined) return ''
  if (typeof value === 'boolean') return value ? 'Evet' : 'Hayır'
  return String(value)
}

const displayedRows = computed(() => {
  let result = props.rows
  for (const col of props.columns) {
    const term = filters[col.key]?.trim().toLowerCase()
    if (term) {
      result = result.filter((row) => cellText(row, col).toLowerCase().includes(term))
    }
  }
  if (sort.value) {
    const { key, direction } = sort.value
    const col = columnsByKey.value[key]
    result = [...result].sort((a, b) => {
      const av = a[key]
      const bv = b[key]
      let cmp: number
      if (typeof av === 'number' && typeof bv === 'number') cmp = av - bv
      else cmp = String(av ?? '').localeCompare(String(bv ?? ''), undefined, { numeric: true })
      return direction === 'asc' ? cmp : -cmp
    })
    void col
  }
  return result
})

function toggleSort(col: ColumnDef) {
  if (col.sortable === false) return
  if (sort.value?.key !== col.key) {
    sort.value = { key: col.key, direction: 'asc' }
  } else if (sort.value.direction === 'asc') {
    sort.value = { key: col.key, direction: 'desc' }
  } else {
    sort.value = null
  }
}

// --- Column drag-reorder -----------------------------------------------
const dragKey = ref<string | null>(null)
function onDragStart(key: string) {
  dragKey.value = key
}
function onDrop(targetKey: string) {
  if (!dragKey.value || dragKey.value === targetKey) return
  const order = [...columnOrder.value]
  const from = order.indexOf(dragKey.value)
  const to = order.indexOf(targetKey)
  order.splice(from, 1)
  order.splice(to, 0, dragKey.value)
  columnOrder.value = order
  dragKey.value = null
  persistLocalLayout()
}

// --- Column resize -------------------------------------------------------
let resizing: { key: string; startX: number; startWidth: number } | null = null
function onResizeStart(key: string, event: MouseEvent) {
  resizing = { key, startX: event.clientX, startWidth: columnWidths[key] ?? 160 }
  window.addEventListener('mousemove', onResizeMove)
  window.addEventListener('mouseup', onResizeEnd)
}
function onResizeMove(event: MouseEvent) {
  if (!resizing) return
  const delta = event.clientX - resizing.startX
  columnWidths[resizing.key] = Math.max(60, resizing.startWidth + delta)
}
function onResizeEnd() {
  resizing = null
  window.removeEventListener('mousemove', onResizeMove)
  window.removeEventListener('mouseup', onResizeEnd)
  persistLocalLayout()
}

// --- Column visibility menu ------------------------------------------------
const columnsMenuOpen = ref(false)
function toggleColumnVisible(key: string) {
  const next = new Set(hiddenColumns.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  hiddenColumns.value = next
  persistLocalLayout()
}

// --- Inline editing ---------------------------------------------------------
const editingCell = ref<{ rowKey: any; column: string } | null>(null)
const editingDraft = ref<any>('')

function startEdit(row: Record<string, any>, col: ColumnDef) {
  if (!col.editable) return
  editingCell.value = { rowKey: row[rowKeyField], column: col.key }
  editingDraft.value = row[col.key]
}
function commitEdit(row: Record<string, any>, col: ColumnDef) {
  if (editingCell.value) {
    emit('cell-edit', { row, column: col.key, value: editingDraft.value })
  }
  editingCell.value = null
}
function cancelEdit() {
  editingCell.value = null
}

// --- Layout persistence (localStorage "last used" + backend saved views) ---
const STORAGE_KEY = `datatable-layout:${props.screenKey}`

function currentLayout() {
  return {
    columnOrder: columnOrder.value,
    hiddenColumns: [...hiddenColumns.value],
    columnWidths: { ...columnWidths },
    sort: sort.value,
    filters: { ...filters },
  }
}

function applyLayout(layout: any) {
  if (!layout) return
  if (Array.isArray(layout.columnOrder)) columnOrder.value = layout.columnOrder
  if (Array.isArray(layout.hiddenColumns)) hiddenColumns.value = new Set(layout.hiddenColumns)
  if (layout.columnWidths) Object.assign(columnWidths, layout.columnWidths)
  if ('sort' in layout) sort.value = layout.sort
  if (layout.filters) {
    for (const k of Object.keys(filters)) delete filters[k]
    Object.assign(filters, layout.filters)
  }
}

function persistLocalLayout() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(currentLayout()))
}
watch(sort, persistLocalLayout)
watch(filters, persistLocalLayout, { deep: true })

// --- Saved views (backend, personal + shared) -------------------------------
interface SavedView {
  id: number
  name: string
  is_shared: boolean
  is_default: boolean
  owner_username: string
  config: any
}
const savedViews = ref<SavedView[]>([])
const activeViewId = ref<number | null>(null)
const viewsMenuOpen = ref(false)
const saveDraftName = ref('')
const saveDraftShared = ref(false)
const showSaveForm = ref(false)

async function fetchSavedViews() {
  const { data } = await apiClient.get('core/saved-views/', { params: { screen_key: props.screenKey } })
  savedViews.value = data.results ?? data
}

function applySavedView(view: SavedView) {
  applyLayout(view.config)
  activeViewId.value = view.id
  persistLocalLayout()
  viewsMenuOpen.value = false
}

async function saveAsNewView() {
  if (!saveDraftName.value.trim()) return
  const { data } = await apiClient.post('core/saved-views/', {
    screen_key: props.screenKey,
    name: saveDraftName.value.trim(),
    is_shared: saveDraftShared.value,
    config: currentLayout(),
  })
  savedViews.value.push(data)
  activeViewId.value = data.id
  saveDraftName.value = ''
  saveDraftShared.value = false
  showSaveForm.value = false
}

async function updateActiveView() {
  if (activeViewId.value === null) return
  const { data } = await apiClient.patch(`core/saved-views/${activeViewId.value}/`, {
    config: currentLayout(),
  })
  const idx = savedViews.value.findIndex((v) => v.id === data.id)
  if (idx !== -1) savedViews.value[idx] = data
}

async function deleteView(view: SavedView) {
  await apiClient.delete(`core/saved-views/${view.id}/`)
  savedViews.value = savedViews.value.filter((v) => v.id !== view.id)
  if (activeViewId.value === view.id) activeViewId.value = null
}

onMounted(async () => {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) {
    try {
      applyLayout(JSON.parse(stored))
    } catch {
      // corrupt/old-shape entry -- ignore, fall through to defaults
    }
  }
  try {
    await fetchSavedViews()
    if (!stored) {
      const defaultView = savedViews.value.find((v) => v.is_default)
      if (defaultView) applySavedView(defaultView)
    }
  } catch {
    // saved views are a convenience layer -- a fetch failure shouldn't
    // block the table itself from rendering with local/default layout
  }
})
</script>

<template>
  <div class="w-full">
    <div class="mb-2 flex items-center gap-2 text-sm">
      <div class="relative">
        <button
          class="rounded border border-neutral-300 px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
          @click="columnsMenuOpen = !columnsMenuOpen"
        >
          Sütunlar
        </button>
        <div
          v-if="columnsMenuOpen"
          class="absolute left-0 z-20 mt-1 w-48 rounded border border-neutral-200 bg-white p-2 shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
        >
          <label
            v-for="col in props.columns"
            :key="col.key"
            class="flex items-center gap-2 px-1 py-1 text-xs text-neutral-700 dark:text-neutral-300"
          >
            <input
              type="checkbox"
              :checked="!hiddenColumns.has(col.key)"
              @change="toggleColumnVisible(col.key)"
            />
            {{ col.label }}
          </label>
        </div>
      </div>

      <div class="relative">
        <button
          class="rounded border border-neutral-300 px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
          @click="viewsMenuOpen = !viewsMenuOpen"
        >
          Görünümler{{ activeViewId ? ': ' + (savedViews.find((v) => v.id === activeViewId)?.name ?? '') : '' }}
        </button>
        <div
          v-if="viewsMenuOpen"
          class="absolute left-0 z-20 mt-1 w-64 rounded border border-neutral-200 bg-white p-2 shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
        >
          <p v-if="savedViews.length === 0" class="px-1 py-1 text-xs text-neutral-500">Henüz kayıtlı görünüm yok.</p>
          <div
            v-for="view in savedViews"
            :key="view.id"
            class="flex items-center justify-between gap-1 rounded px-1 py-1 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            <button class="flex-1 text-left" @click="applySavedView(view)">
              {{ view.name }}
              <span class="text-neutral-400">{{ view.is_shared ? '(paylaşılan)' : '(kişisel)' }}</span>
            </button>
            <button class="text-neutral-400 hover:text-red-600" title="Sil" @click="deleteView(view)">✕</button>
          </div>

          <div class="mt-2 border-t border-neutral-200 pt-2 dark:border-neutral-700">
            <button
              v-if="activeViewId !== null"
              class="mb-1 w-full rounded bg-neutral-100 px-2 py-1 text-left text-xs hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700"
              @click="updateActiveView"
            >
              Geçerli görünümü güncelle
            </button>
            <button
              v-if="!showSaveForm"
              class="w-full rounded bg-neutral-100 px-2 py-1 text-left text-xs hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700"
              @click="showSaveForm = true"
            >
              + Yeni görünüm kaydet
            </button>
            <div v-else class="space-y-1">
              <input
                v-model="saveDraftName"
                placeholder="Görünüm adı"
                class="w-full rounded border border-neutral-300 px-2 py-1 text-xs dark:border-neutral-700 dark:bg-neutral-800"
              />
              <label class="flex items-center gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                <input v-model="saveDraftShared" type="checkbox" />
                Herkese açık (paylaşılan)
              </label>
              <button class="w-full rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700" @click="saveAsNewView">
                Kaydet
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="overflow-x-auto rounded border border-neutral-200 dark:border-neutral-800">
      <table class="w-full text-left text-sm">
        <thead>
          <tr class="border-b border-neutral-200 bg-neutral-50 text-neutral-600 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-400">
            <th
              v-for="col in visibleColumns"
              :key="col.key"
              draggable="true"
              class="relative select-none px-3 py-2 font-medium"
              :style="{ width: (columnWidths[col.key] ?? 160) + 'px' }"
              @dragstart="onDragStart(col.key)"
              @dragover.prevent
              @drop="onDrop(col.key)"
            >
              <button
                class="flex w-full items-center gap-1 text-left"
                :class="col.sortable === false ? 'cursor-default' : 'cursor-pointer hover:text-neutral-900 dark:hover:text-neutral-100'"
                @click="toggleSort(col)"
              >
                <span class="truncate">{{ col.label }}</span>
                <span v-if="sort?.key === col.key" class="text-[10px]">{{ sort.direction === 'asc' ? '▲' : '▼' }}</span>
              </button>
              <div
                v-if="col.filterable !== false"
                class="mt-1"
              >
                <input
                  v-model="filters[col.key]"
                  type="text"
                  placeholder="Filtrele..."
                  class="w-full rounded border border-neutral-200 bg-white px-1 py-0.5 text-xs font-normal text-neutral-700 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300"
                  @click.stop
                />
              </div>
              <div
                class="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-blue-400"
                @mousedown.stop="onResizeStart(col.key, $event)"
              />
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in displayedRows"
            :key="row[rowKeyField]"
            class="border-b border-neutral-100 last:border-0 dark:border-neutral-900"
          >
            <td
              v-for="col in visibleColumns"
              :key="col.key"
              class="px-3 py-1.5 text-neutral-800 dark:text-neutral-200"
              :class="col.editable && !$slots[col.key] ? 'cursor-text' : ''"
              @click="$slots[col.key] ? undefined : startEdit(row, col)"
            >
              <!-- Custom per-column rendering (status badges, action buttons,
                   etc.) -- a screen provides `<template #columnKey="{ row, value }">`;
                   falls back to the generic text/inline-edit cell otherwise.
                   Slotted columns opt out of built-in inline editing (the
                   screen owns that cell's interaction entirely). -->
              <slot v-if="$slots[col.key]" :name="col.key" :row="row" :value="row[col.key]" />
              <template v-else-if="editingCell !== null && editingCell.rowKey === row[rowKeyField] && editingCell.column === col.key">
                <select
                  v-if="col.type === 'select' || col.type === 'boolean'"
                  v-model="editingDraft"
                  class="w-full rounded border border-blue-400 px-1 py-0.5 text-sm dark:bg-neutral-800"
                  autofocus
                  @change="commitEdit(row, col)"
                  @blur="commitEdit(row, col)"
                  @keydown.escape="cancelEdit"
                >
                  <option
                    v-for="opt in col.type === 'boolean' ? [{ value: true, label: 'Evet' }, { value: false, label: 'Hayır' }] : col.options"
                    :key="String(opt.value)"
                    :value="opt.value"
                  >
                    {{ opt.label }}
                  </option>
                </select>
                <input
                  v-else
                  v-model="editingDraft"
                  :type="col.type === 'number' ? 'number' : 'text'"
                  class="w-full rounded border border-blue-400 px-1 py-0.5 text-sm dark:bg-neutral-800"
                  autofocus
                  @keydown.enter="commitEdit(row, col)"
                  @keydown.escape="cancelEdit"
                  @blur="commitEdit(row, col)"
                />
              </template>
              <template v-else>
                {{ cellText(row, col) }}
              </template>
            </td>
          </tr>
          <tr v-if="displayedRows.length === 0">
            <td :colspan="visibleColumns.length" class="px-3 py-6 text-center text-neutral-400">Kayıt yok.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
