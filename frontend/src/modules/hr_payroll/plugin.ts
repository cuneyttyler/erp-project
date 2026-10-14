import { CalendarDaysIcon, CurrencyDollarIcon, UserGroupIcon } from '@heroicons/vue/24/outline'

import type { PluginManifest } from '@/plugins/types'

export const hrPayrollPlugin: PluginManifest = {
  key: 'hr_payroll',
  package: 'hr_payroll',
  icon: UserGroupIcon,
  navGroup: 'hr',
  pages: [
    { path: '/employees', action: 'employee.view', name: 'employees', labelKey: 'nav.employees', icon: UserGroupIcon, component: () => import('./views/EmployeesView.vue') },
    { path: '/leave-requests', action: 'leave_request.view', name: 'leave-requests', labelKey: 'nav.leaveRequests', icon: CalendarDaysIcon, component: () => import('./views/LeaveRequestsView.vue') },
    { path: '/payroll-runs', action: 'payroll_run.view', name: 'payroll-runs', labelKey: 'nav.payrollRuns', icon: CurrencyDollarIcon, component: () => import('./views/PayrollRunsView.vue') },
  ],
}
