import type { ValueFormat } from './format'

// The payload shapes of GET plugins/widgets/<key>/data/ -- one per widget
// kind, mirroring the helpers at the bottom of
// backend/apps/plugins/registry.py.

export interface StatData {
  kind: 'stat'
  value: string
  format: ValueFormat
  secondary: { key: string; value: string; format: ValueFormat }[]
  delta: { percent: string; compare_key: string; good_when: 'up' | 'down' } | null
  trend: { label: string; value: string }[]
  route: string | null
}

export type LabelKind = 'month' | 'date' | 'key' | 'text'

export interface ChartData {
  kind: 'chart'
  chart: 'line' | 'bar' | 'hbar'
  format: ValueFormat
  label_kind: LabelKind
  series: { key: string; points: { label: string; value: string }[] }[]
  route: string | null
}

export type ColumnKind = 'text' | 'money' | 'number' | 'date' | 'datetime' | 'status'

export interface TableData {
  kind: 'table'
  columns: { key: string; kind: ColumnKind }[]
  rows: Record<string, string | number | null>[]
  total_count: number
  route: string | null
}

export type Severity = 'critical' | 'warning' | 'info'

export interface AttentionData {
  kind: 'attention'
  items: { key: string; count: number; severity: Severity; route: string; amount: string | null }[]
}

export interface QuickActionsData {
  kind: 'quick_actions'
}

export type WidgetData = StatData | ChartData | TableData | AttentionData | QuickActionsData
