<script setup lang="ts">
import { XMarkIcon } from '@heroicons/vue/24/outline'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// A centered dialog over a dimmed page. Closes on Escape, on the close
// button and on a click on the backdrop -- never on a click inside, so a
// stray click while filling a form doesn't throw the form away.
defineProps<{ title: string; wide?: boolean }>()
const emit = defineEmits<{ close: [] }>()

const panel = ref<HTMLElement | null>(null)

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  panel.value?.focus()
})
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:p-8" @mousedown.self="emit('close')">
    <div
      ref="panel"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
      tabindex="-1"
      class="w-full rounded-lg border border-neutral-200 bg-white shadow-xl outline-none dark:border-neutral-800 dark:bg-neutral-900"
      :class="wide ? 'max-w-4xl' : 'max-w-xl'"
    >
      <header class="flex items-center justify-between border-b border-neutral-200 px-5 py-3 dark:border-neutral-800">
        <h2 class="text-base font-semibold text-neutral-900 dark:text-neutral-100">{{ title }}</h2>
        <button
          class="rounded p-1 text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 dark:hover:bg-neutral-800 dark:hover:text-neutral-100"
          :aria-label="t('common.close')"
          @click="emit('close')"
        >
          <XMarkIcon class="h-5 w-5" />
        </button>
      </header>
      <div class="px-5 py-4">
        <slot />
      </div>
      <footer v-if="$slots.footer" class="flex items-center justify-end gap-2 border-t border-neutral-200 px-5 py-3 dark:border-neutral-800">
        <slot name="footer" />
      </footer>
    </div>
  </div>
</template>
