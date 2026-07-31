import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export interface Employee {
  id: number
  first_name: string
  last_name: string
  national_id: string
  position: string
  department: string
  hire_date: string
  monthly_gross_salary: string
  is_active: boolean
}

export type LeaveType = 'annual' | 'sick'
export type LeaveStatus = 'pending' | 'approved' | 'rejected'

export interface LeaveRequest {
  id: number
  employee: number
  employee_name: string
  leave_type: LeaveType
  start_date: string
  end_date: string
  days: number
  status: LeaveStatus
  reason: string
  created_at: string
}

export interface Payslip {
  id: number
  employee: number
  employee_name: string
  gross_salary: string
  sgk_employee_premium: string
  unemployment_employee_premium: string
  income_tax: string
  stamp_duty: string
  net_salary: string
  employer_sgk_cost: string
  employer_unemployment_cost: string
  total_employer_cost: string
}

export type PayrollRunStatus = 'draft' | 'finalized'

export interface PayrollRun {
  id: number
  period_year: number
  period_month: number
  status: PayrollRunStatus
  payslips: Payslip[]
  created_at: string
}

// HR & Payroll package state (REQ-HR-001/002/003) -- src/modules/hr_payroll/,
// a real independently-priced Package (product.md §6.2).
export const useHrPayrollStore = defineStore('hrPayroll', () => {
  const employees = ref<Employee[]>([])
  const leaveRequests = ref<LeaveRequest[]>([])
  const payrollRuns = ref<PayrollRun[]>([])

  async function fetchEmployees() {
    const { data } = await apiClient.get('hr-payroll/employees/', { params: { page_size: 100 } })
    employees.value = data.results ?? data
  }

  async function createEmployee(payload: {
    first_name: string
    last_name: string
    position: string
    department: string
    hire_date: string
    monthly_gross_salary: string
  }) {
    const { data } = await apiClient.post<Employee>('hr-payroll/employees/', payload)
    employees.value.unshift(data)
    return data
  }

  async function fetchLeaveRequests() {
    const { data } = await apiClient.get('hr-payroll/leave-requests/', { params: { page_size: 100 } })
    leaveRequests.value = data.results ?? data
  }

  async function createLeaveRequest(payload: {
    employee: number
    leave_type: LeaveType
    start_date: string
    end_date: string
    reason: string
  }) {
    const { data } = await apiClient.post<LeaveRequest>('hr-payroll/leave-requests/', payload)
    leaveRequests.value.unshift(data)
    return data
  }

  function replaceLeaveRequest(leave: LeaveRequest) {
    const idx = leaveRequests.value.findIndex((l) => l.id === leave.id)
    if (idx !== -1) leaveRequests.value[idx] = leave
  }

  async function approveLeaveRequest(id: number) {
    const { data } = await apiClient.post<LeaveRequest>(`hr-payroll/leave-requests/${id}/approve/`)
    replaceLeaveRequest(data)
    return data
  }

  async function rejectLeaveRequest(id: number) {
    const { data } = await apiClient.post<LeaveRequest>(`hr-payroll/leave-requests/${id}/reject/`)
    replaceLeaveRequest(data)
    return data
  }

  async function fetchPayrollRuns() {
    const { data } = await apiClient.get('hr-payroll/payroll-runs/', { params: { page_size: 50 } })
    payrollRuns.value = data.results ?? data
  }

  async function createPayrollRun(period_year: number, period_month: number) {
    const { data } = await apiClient.post<PayrollRun>('hr-payroll/payroll-runs/', { period_year, period_month })
    payrollRuns.value.unshift(data)
    return data
  }

  function replacePayrollRun(run: PayrollRun) {
    const idx = payrollRuns.value.findIndex((r) => r.id === run.id)
    if (idx !== -1) payrollRuns.value[idx] = run
  }

  async function calculatePayrollRun(id: number) {
    const { data } = await apiClient.post<PayrollRun>(`hr-payroll/payroll-runs/${id}/calculate/`)
    replacePayrollRun(data)
    return data
  }

  async function finalizePayrollRun(id: number) {
    const { data } = await apiClient.post<PayrollRun>(`hr-payroll/payroll-runs/${id}/finalize/`)
    replacePayrollRun(data)
    return data
  }

  return {
    employees,
    leaveRequests,
    payrollRuns,
    fetchEmployees,
    createEmployee,
    fetchLeaveRequests,
    createLeaveRequest,
    approveLeaveRequest,
    rejectLeaveRequest,
    fetchPayrollRuns,
    createPayrollRun,
    calculatePayrollRun,
    finalizePayrollRun,
  }
})
