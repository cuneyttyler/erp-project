<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import ChartTile from '@/shared/components/ChartTile.vue'
import { useBIStore, type Dashboard, type SeriesPoint } from '@/modules/bi/stores/bi'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-BI-001's "dashboard builder": pick a dashboard, add/remove saved
// reports as tiles, drag tiles to reorder (native HTML5 DnD -- the actual
// "drag-and-drop" the requirement names, not a euphemism for up/down buttons).
const bi = useBIStore()

onMounted(() => {
  bi.fetchDashboards()
  bi.fetchReports()
})

const newDashboardName = ref('')
const currentDashboardId = ref<number | null>(null)
const error = ref('')

async function createDashboard() {
  if (!newDashboardName.value.trim()) return
  const dashboard = await bi.createDashboard({ name: newDashboardName.value })
  newDashboardName.value = ''
  currentDashboardId.value = dashboard.id
}

function selectDashboard(id: number) {
  currentDashboardId.value = id
}

function currentDashboard(): Dashboard | undefined {
  return bi.dashboards.find((d) => d.id === currentDashboardId.value)
}

const addReportId = ref<number | null>(null)
async function addTile() {
  if (currentDashboardId.value === null || addReportId.value === null) return
  try {
    await bi.addTile(currentDashboardId.value, addReportId.value)
    addReportId.value = null
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('biDashboards.errors.add')
  }
}

async function removeTile(tileId: number) {
  if (currentDashboardId.value === null) return
  await bi.removeTile(currentDashboardId.value, tileId)
}

const tileData = reactive<Record<number, SeriesPoint[]>>({})
async function loadTileData(tileId: number, seriesName: string, params: Record<string, unknown>) {
  if (tileData[tileId]) return
  const result = await bi.runSeries(seriesName, params)
  tileData[tileId] = result.series
}

const draggingTileId = ref<number | null>(null)

function onDragStart(tileId: number) {
  draggingTileId.value = tileId
}

async function onDrop(targetTileId: number) {
  const dashboard = currentDashboard()
  if (!dashboard || draggingTileId.value === null || draggingTileId.value === targetTileId) return
  const ids = dashboard.tiles.map((t) => t.id)
  const fromIdx = ids.indexOf(draggingTileId.value)
  const toIdx = ids.indexOf(targetTileId)
  ids.splice(toIdx, 0, ids.splice(fromIdx, 1)[0])
  const order = ids.map((id, position) => ({ tile_id: id, position }))
  draggingTileId.value = null
  await bi.reorderTiles(dashboard.id, order)
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('biDashboards.title') }}</h1>

    <div class="mt-4 flex items-center gap-2">
      <select :value="currentDashboardId" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" @change="selectDashboard(Number(($event.target as HTMLSelectElement).value))">
        <option :value="null" disabled>{{ t('biDashboards.select') }}</option>
        <option v-for="d in bi.dashboards" :key="d.id" :value="d.id">{{ d.name }}</option>
      </select>
      <input v-model="newDashboardName" :placeholder="t('biDashboards.newName')" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
      <button class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700" @click="createDashboard">{{ t('biDashboards.create') }}</button>
    </div>

    <template v-if="currentDashboard()">
      <div class="mt-4 flex items-center gap-2">
        <select v-model.number="addReportId" class="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800">
          <option :value="null" disabled>{{ t('biDashboards.selectReport') }}</option>
          <option v-for="r in bi.reports" :key="r.id" :value="r.id">{{ r.name }}</option>
        </select>
        <button class="rounded bg-neutral-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-900" @click="addTile">{{ t('biDashboards.addToDashboard') }}</button>
      </div>
      <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>

      <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="tile in currentDashboard()!.tiles"
          :key="tile.id"
          draggable="true"
          class="relative cursor-move"
          @dragstart="onDragStart(tile.id)"
          @dragover.prevent
          @drop="onDrop(tile.id)"
          @mouseenter="loadTileData(tile.id, tile.report.series_name, tile.report.params)"
        >
          <button class="absolute right-2 top-2 z-10 rounded bg-neutral-200 px-1.5 py-0.5 text-xs text-neutral-700 hover:bg-neutral-300 dark:bg-neutral-700 dark:text-neutral-200" @click="removeTile(tile.id)">✕</button>
          <ChartTile
            v-if="tileData[tile.id]"
            :title="tile.report.name"
            :chart-kind="tile.report.chart_type === 'line' ? 'time' : 'category'"
            :data="tileData[tile.id]"
          />
          <div v-else class="flex h-40 items-center justify-center rounded border border-neutral-200 text-sm text-neutral-400 dark:border-neutral-800">
            {{ tile.report.name }}
          </div>
        </div>
      </div>
    </template>
  </section>
</template>
