<script setup lang="ts">
import { computed } from 'vue'

// The assistant's reply text. Models like to mark a key figure in
// **bold**; that one piece of Markdown is rendered, and everything else is
// shown exactly as written. The text is split into plain and bold segments
// and rendered as text nodes -- never as HTML -- so nothing a model (or a
// record name it quotes) contains can inject markup.
const props = defineProps<{ text: string }>()

const segments = computed(() =>
  props.text
    .split(/(\*\*[^*\n]+\*\*)/g)
    .filter((part) => part !== '')
    .map((part) => (part.startsWith('**') && part.endsWith('**') && part.length > 4 ? { bold: true, text: part.slice(2, -2) } : { bold: false, text: part })),
)
</script>

<template>
  <p class="whitespace-pre-wrap text-sm leading-relaxed text-neutral-900 dark:text-neutral-100">
    <template v-for="(segment, index) in segments" :key="index">
      <strong v-if="segment.bold" class="font-semibold">{{ segment.text }}</strong>
      <template v-else>{{ segment.text }}</template>
    </template>
  </p>
</template>
