<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import ChartTile from '@/shared/components/ChartTile.vue'
import { useBIStore, type ChartType, type SeriesPoint } from '@/modules/bi/stores/bi'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// REQ-BI-001/003: pick a registered series, save it as a named report
// (personal or shared), preview it live before saving.
const bi = useBIStore()

onMounted(() => {
  bi.fetchAvailableSeries()
  bi.fetchReports()
})

const form = reactive({
  name: '',
  series_name: '',
  chart_type: 'bar' as ChartType,
  is_shared: false,
})
const error = ref('')
const previewData = ref<SeriesPoint[] | null>(null)
const previewing = ref(false)

async function preview() {
  if (!form.series_name) return
  previewing.value = true
  try {
    const result = await bi.runSeries(form.series_name)
    previewData.value = result.series
    form.chart_type = result.chart_kind === 'time' ? 'line' : 'bar'
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('biReports.errors.preview')
  } finally {
    previewing.value = false
  }
}

async function submit() {
  error.value = ''
  if (!form.name.trim() || !form.series_name) {
    error.value = t('biReports.errors.required')
    return
  }
  try {
    await bi.createReport({ ...form })
    form.name = ''
    previewData.value = null
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? t('biReports.errors.save')
  }
}

const reportPreviews = reactive<Record<number, SeriesPoint[]>>({})
async function loadReportPreview(reportId: number, seriesName: string, params: Record<string, unknown>) {
  if (reportPreviews[reportId]) return
  const result = await bi.runSeries(seriesName, params)
  reportPreviews[reportId] = result.series
}
</script>

<template>
  <section class="p-8">
    <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('biReports.title') }}</h1>
    <p class="mt-1 text-sm text-neutral-500">
      {{ t('biReports.subtitle') }}
    </p>

    <div class="mt-4 grid grid-cols-2 gap-6">
      <form class="rounded border border-neutral-200 p-4 dark:border-neutral-800" @submit.prevent="submit">
        <div>
          <label class="mb-1 block text-xs text-neutral-500">{{ t('biReports.series') }}</label>
          <select v-model="form.series_name" class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" @change="preview">
            <option value="" disabled>{{ t('common.select') }}</option>
            <option v-for="s in bi.availableSeries" :key="s.name" :value="s.name">{{ s.description }}</option>
          </select>
        </div>
        <div class="mt-2">
          <label class="mb-1 block text-xs text-neutral-500">{{ t('biReports.name') }}</label>
          <input v-model="form.name" class="w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800" />
        </div>
        <label class="mt-2 flex items-center gap-2 text-sm">
          <input v-model="form.is_shared" type="checkbox" />
          {{ t('biReports.share') }}
        </label>
        <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
        <button type="submit" class="mt-3 rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">{{ t('common.save') }}</button>
      </form>

      <div>
        <ChartTile
          v-if="previewData"
          :title="t('biReports.preview')"
          :chart-kind="form.chart_type === 'line' ? 'time' : 'category'"
          :data="previewData"
        />
        <p v-else-if="previewing" class="text-sm text-neutral-500">{{ t('common.loading') }}</p>
      </div>
    </div>

    <h2 class="mt-8 text-sm font-semibold text-neutral-700 dark:text-neutral-300">{{ t('biReports.saved') }}</h2>
    <div class="mt-2 grid grid-cols-2 gap-4 lg:grid-cols-3">
      <div v-for="r in bi.reports" :key="r.id" @mouseenter="loadReportPreview(r.id, r.series_name, r.params)">
        <ChartTile v-if="reportPreviews[r.id]" :title="r.name" :chart-kind="r.chart_type === 'line' ? 'time' : 'category'" :data="reportPreviews[r.id]" />
        <div v-else class="flex h-40 items-center justify-center rounded border border-neutral-200 text-sm text-neutral-400 dark:border-neutral-800">
          {{ r.name }}
        </div>
      </div>
    </div>
  </section>
</template>
