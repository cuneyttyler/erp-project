import { PresentationChartLineIcon, Squares2X2Icon } from '@heroicons/vue/24/outline'

import type { PluginManifest } from '@/plugins/types'

export const biPlugin: PluginManifest = {
  key: 'bi_analytics',
  package: 'bi_analytics',
  icon: PresentationChartLineIcon,
  navGroup: 'bi',
  pages: [
    { path: '/bi/reports', action: 'saved_report.view', name: 'bi-reports', labelKey: 'nav.biReports', icon: PresentationChartLineIcon, component: () => import('./views/BIReportsView.vue') },
    { path: '/bi/dashboards', action: 'bi_dashboard.view', name: 'bi-dashboards', labelKey: 'nav.biDashboards', icon: Squares2X2Icon, component: () => import('./views/BIDashboardsView.vue') },
  ],
}
