<script setup lang="ts">
import { PaperAirplaneIcon, PencilSquareIcon, SparklesIcon, TrashIcon } from '@heroicons/vue/24/outline'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useActionLabels } from '@/core/access/labels'
import { useAuthStore } from '@/shared/stores/auth'

import FieldList from './blocks/FieldList.vue'
import ProposalCard from './blocks/ProposalCard.vue'
import ResultChart from './blocks/ResultChart.vue'
import ResultTable from './blocks/ResultTable.vue'
import RichText from './blocks/RichText.vue'
import { useAIStore } from './store'

// The AI assistant (REQ-CORE-AI-001), as a full page rather than a side
// panel: its answers are tables, charts and approval cards, which need the
// room. Conversations are listed on the left and kept on the server, so a
// user can come back to one -- and to a proposal still waiting in it.
//
// What the assistant can read and propose is exactly what the signed-in
// user may do; anything it proposes happens only when someone approves the
// card (see blocks/ProposalCard.vue).
const { t, locale } = useI18n()
const ai = useAIStore()
const auth = useAuthStore()
const labels = useActionLabels()

const draft = ref('')
const thread = ref<HTMLElement | null>(null)
const input = ref<HTMLTextAreaElement | null>(null)

onMounted(() => {
  ai.fetchConversations().catch(() => undefined)
  input.value?.focus()
})

// Keep the newest message in view as the thread grows.
watch(
  () => [ai.messages.length, ai.isThinking],
  async () => {
    await nextTick()
    thread.value?.scrollTo({ top: thread.value.scrollHeight, behavior: 'smooth' })
  },
)

function submit() {
  const text = draft.value.trim()
  if (!text || ai.isThinking) return
  draft.value = ''
  ai.send(text)
}

function onKeydown(event: KeyboardEvent) {
  // Enter sends; Shift+Enter makes a new line.
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submit()
  }
}

function ask(example: string) {
  draft.value = example
  submit()
}

// A few starting points, limited to things this user can actually do.
const examples = computed(() =>
  [
    { action: 'ar_aging.view', key: 'overdue' },
    { action: 'trial_balance.view', key: 'cash' },
    { action: 'invoice.view', key: 'topCustomers' },
    { action: 'account.view', key: 'accounts' },
    { action: 'item.create', key: 'newItem' },
    { action: 'invoice.create', key: 'newInvoice' },
    { action: 'stock_level.view', key: 'lowStock' },
    { action: 'leave_request.approve', key: 'leave' },
  ]
    .filter((example) => auth.can(example.action))
    .slice(0, 4)
    .map((example) => t(`assistant.examples.${example.key}`)),
)

function relativeDay(iso: string): string {
  return new Intl.DateTimeFormat(locale.value === 'tr' ? 'tr-TR' : 'en-GB', { day: 'numeric', month: 'short' }).format(new Date(iso))
}

const pendingDelete = ref<number | null>(null)
async function remove(id: number) {
  // Two clicks rather than a dialog: the first arms the button.
  if (pendingDelete.value !== id) {
    pendingDelete.value = id
    return
  }
  pendingDelete.value = null
  await ai.remove(id).catch(() => undefined)
}
</script>

<template>
  <section class="flex h-full">
    <!-- Conversations -->
    <aside class="hidden w-64 shrink-0 flex-col border-r border-neutral-200 bg-white lg:flex dark:border-neutral-800 dark:bg-neutral-900">
      <div class="p-3">
        <button
          class="flex w-full items-center justify-center gap-1.5 rounded border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-800 hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-200 dark:hover:bg-neutral-800"
          @click="((ai.startNew()), input?.focus())"
        >
          <PencilSquareIcon class="h-4 w-4" />{{ t('assistant.newChat') }}
        </button>
      </div>
      <p v-if="ai.conversations.length === 0" class="px-4 py-2 text-sm text-neutral-500">{{ t('assistant.noConversations') }}</p>
      <ul class="flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
        <li v-for="conversation in ai.conversations" :key="conversation.id" class="group relative">
          <button
            class="w-full rounded px-2 py-1.5 pr-8 text-left text-sm"
            :class="
              ai.currentId === conversation.id
                ? 'bg-blue-50 text-blue-800 dark:bg-blue-950 dark:text-blue-200'
                : 'text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800'
            "
            @click="ai.open(conversation.id)"
          >
            <span class="block truncate">{{ conversation.title }}</span>
            <span class="block text-xs text-neutral-500">{{ relativeDay(conversation.updated_at) }}</span>
          </button>
          <button
            class="absolute right-1 top-1.5 rounded p-1 opacity-0 focus:opacity-100 group-hover:opacity-100"
            :class="pendingDelete === conversation.id ? 'bg-red-600 text-white opacity-100' : 'text-neutral-500 hover:bg-neutral-200 dark:hover:bg-neutral-700'"
            :aria-label="pendingDelete === conversation.id ? t('assistant.confirmDelete') : t('assistant.delete')"
            :title="pendingDelete === conversation.id ? t('assistant.confirmDelete') : t('assistant.delete')"
            @click="remove(conversation.id)"
            @blur="pendingDelete = null"
          >
            <TrashIcon class="h-4 w-4" />
          </button>
        </li>
      </ul>
    </aside>

    <!-- Thread -->
    <div class="flex min-w-0 flex-1 flex-col">
      <div ref="thread" class="flex-1 overflow-y-auto">
        <div class="mx-auto max-w-4xl px-4 py-6 lg:px-8">
          <!-- Empty state -->
          <div v-if="ai.messages.length === 0 && !ai.isLoadingConversation" class="pt-10 text-center">
            <span class="inline-flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
              <SparklesIcon class="h-6 w-6" />
            </span>
            <h1 class="mt-3 text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('assistant.title') }}</h1>
            <p class="mx-auto mt-1 max-w-xl text-sm text-neutral-600 dark:text-neutral-400">{{ t('assistant.intro') }}</p>
            <div v-if="examples.length" class="mx-auto mt-6 grid max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2">
              <button
                v-for="example in examples"
                :key="example"
                class="rounded-lg border border-neutral-200 bg-white px-3 py-2.5 text-left text-sm text-neutral-800 hover:border-blue-300 hover:bg-blue-50 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:border-blue-800 dark:hover:bg-blue-950"
                @click="ask(example)"
              >
                {{ example }}
              </button>
            </div>
          </div>

          <p v-if="ai.isLoadingConversation" class="pt-10 text-center text-sm text-neutral-500">{{ t('access.loading') }}</p>

          <div class="space-y-5">
            <template v-for="message in ai.messages" :key="message.id">
              <div v-if="message.role === 'user'" class="flex justify-end">
                <p class="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-blue-600 px-4 py-2 text-sm text-white">{{ message.text }}</p>
              </div>
              <div v-else class="flex gap-3">
                <span class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                  <SparklesIcon class="h-4 w-4" />
                </span>
                <div class="min-w-0 flex-1 space-y-3">
                  <RichText :text="message.text" />
                  <template v-for="(block, index) in message.blocks" :key="index">
                    <ResultTable v-if="block.type === 'table'" :block="block" />
                    <ResultChart v-else-if="block.type === 'chart'" :block="block" />
                    <ProposalCard v-else-if="block.type === 'proposal'" :proposal="block.approval" />
                    <figure v-else-if="block.type === 'record'" class="rounded-lg border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900">
                      <figcaption class="mb-2 text-sm font-medium text-neutral-800 dark:text-neutral-200">{{ labels.resource(block.resource) }} #{{ block.id }}</figcaption>
                      <FieldList :fields="block.fields" />
                    </figure>
                  </template>
                  <!-- REQ-CORE-AI-003: where a figure came from, as a link to that screen -->
                  <p v-if="message.citations.length" class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-neutral-500">
                    {{ t('assistant.sources') }}
                    <RouterLink v-for="citation in message.citations" :key="citation.route" :to="citation.route" class="font-medium text-blue-700 hover:underline dark:text-blue-400">
                      {{ citation.label }}
                    </RouterLink>
                  </p>
                </div>
              </div>
            </template>

            <div v-if="ai.isThinking" class="flex items-center gap-3" aria-live="polite">
              <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                <SparklesIcon class="h-4 w-4 animate-pulse" />
              </span>
              <span class="text-sm text-neutral-500">{{ t('assistant.thinking') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Composer -->
      <div class="border-t border-neutral-200 bg-white px-4 py-3 lg:px-8 dark:border-neutral-800 dark:bg-neutral-900">
        <form class="mx-auto flex max-w-4xl items-end gap-2" @submit.prevent="submit">
          <textarea
            ref="input"
            v-model="draft"
            rows="2"
            :placeholder="t('assistant.placeholder')"
            :aria-label="t('assistant.placeholder')"
            class="max-h-40 flex-1 resize-none rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-800"
            @keydown="onKeydown"
          />
          <button
            type="submit"
            class="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="ai.isThinking || !draft.trim()"
          >
            <PaperAirplaneIcon class="h-4 w-4" />{{ t('assistant.send') }}
          </button>
        </form>
        <p class="mx-auto mt-1.5 max-w-4xl text-xs text-neutral-500">{{ t('assistant.footnote') }}</p>
      </div>
    </div>
  </section>
</template>
