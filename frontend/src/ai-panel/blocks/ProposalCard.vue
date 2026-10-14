<script setup lang="ts">
import { CheckCircleIcon, ExclamationTriangleIcon, HandRaisedIcon, XCircleIcon } from '@heroicons/vue/24/outline'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useActionLabels } from '@/core/access/labels'

import { useAIStore, type Proposal } from '../store'
import FieldList from './FieldList.vue'
import { useValues } from './values'

// A change the assistant wants to make, waiting for a person's decision
// (REQ-CORE-AI-007, REQ-AI-XCUT-003). The card says exactly what will
// happen -- the action, the record, and the data or the field-by-field
// changes -- and it must never look like something already done: it's a
// distinct amber "needs you" card until it's resolved, and only then turns
// into a quiet statement of the outcome.
const props = defineProps<{ proposal: Proposal }>()

const { t } = useI18n()
const ai = useAIStore()
const labels = useActionLabels()
const values = useValues()

const isResolving = ref(false)
const error = ref('')

const changes = computed(() => props.proposal.preview.changes ?? [])
const hasData = computed(() => Object.keys(props.proposal.action_input ?? {}).length > 0)
const target = computed(() => props.proposal.preview.target_label || (props.proposal.target_id ? `#${props.proposal.target_id}` : ''))

async function resolve(decision: 'approve' | 'reject') {
  if (isResolving.value) return
  isResolving.value = true
  error.value = (await ai.resolve(props.proposal, decision)) ?? ''
  isResolving.value = false
}
</script>

<template>
  <section
    class="rounded-lg border p-3"
    :class="
      proposal.status === 'pending'
        ? 'border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40'
        : 'border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900'
    "
  >
    <header class="flex items-start gap-2">
      <HandRaisedIcon v-if="proposal.status === 'pending'" class="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
      <CheckCircleIcon v-else-if="proposal.status === 'executed'" class="mt-0.5 h-5 w-5 shrink-0 text-green-600 dark:text-green-500" />
      <ExclamationTriangleIcon v-else-if="proposal.status === 'failed'" class="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-400" />
      <XCircleIcon v-else class="mt-0.5 h-5 w-5 shrink-0 text-neutral-400" />
      <div class="min-w-0">
        <p class="text-xs font-medium text-neutral-600 dark:text-neutral-400">{{ t(`assistant.proposal.status.${proposal.status}`) }}</p>
        <p class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
          {{ labels.action(proposal.action_name) }}<template v-if="target"> · {{ target }}</template>
        </p>
        <p v-if="proposal.preview.reason" class="mt-0.5 text-sm text-neutral-700 dark:text-neutral-300">{{ proposal.preview.reason }}</p>
      </div>
    </header>

    <!-- An edit shows only what changes, old value to new. -->
    <table v-if="changes.length" class="mt-3 w-full text-sm">
      <thead>
        <tr class="text-xs text-neutral-500">
          <th class="pb-1 pr-3 text-left font-medium">{{ t('audit.columns.field') }}</th>
          <th class="pb-1 pr-3 text-left font-medium">{{ t('audit.columns.before') }}</th>
          <th class="pb-1 text-left font-medium">{{ t('audit.columns.after') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="change in changes" :key="change.field" class="align-top">
          <td class="py-0.5 pr-3 text-neutral-600 dark:text-neutral-400">{{ values.label(change.field) }}</td>
          <td class="py-0.5 pr-3 text-neutral-600 line-through decoration-neutral-400 dark:text-neutral-400">{{ values.text(change.field, change.before) }}</td>
          <td class="py-0.5 font-medium text-neutral-900 dark:text-neutral-100">{{ values.text(change.field, change.after) }}</td>
        </tr>
      </tbody>
    </table>
    <FieldList v-else-if="hasData" :fields="proposal.action_input" class="mt-3" />

    <p v-if="proposal.status === 'failed'" class="mt-3 text-sm text-red-700 dark:text-red-300">{{ t('assistant.proposal.failedBecause') }} {{ proposal.error }}</p>
    <p v-if="error" class="mt-3 text-sm text-red-700 dark:text-red-300" role="alert">{{ error }}</p>

    <footer v-if="proposal.status === 'pending'" class="mt-3 flex flex-wrap items-center gap-2">
      <template v-if="proposal.can_approve">
        <button
          class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="isResolving"
          @click="resolve('approve')"
        >
          {{ t('assistant.proposal.approve') }}
        </button>
        <button
          class="rounded border border-neutral-300 bg-white px-3 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:bg-neutral-800"
          :disabled="isResolving"
          @click="resolve('reject')"
        >
          {{ t('assistant.proposal.reject') }}
        </button>
        <span class="text-xs text-neutral-600 dark:text-neutral-400">{{ t('assistant.proposal.nothingYet') }}</span>
      </template>
      <span v-else class="text-xs text-neutral-600 dark:text-neutral-400">{{ t('assistant.proposal.noPermission') }}</span>
    </footer>
    <p v-else-if="proposal.status === 'executed'" class="mt-3 text-xs text-neutral-500">
      {{ t('assistant.proposal.doneBy', { user: proposal.resolved_by_username }) }}
      <RouterLink :to="{ name: 'audit-log', query: {} }" class="font-medium text-blue-700 hover:underline dark:text-blue-400">{{ t('assistant.proposal.seeAudit') }}</RouterLink>
    </p>
  </section>
</template>
