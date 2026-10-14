<script setup lang="ts">
// The ERPIntel mark and wordmark. The mark is the same drawing as
// public/favicon.svg, inlined so it needs no request and scales crisply.
withDefaults(defineProps<{ markOnly?: boolean; size?: 'sm' | 'md' }>(), { markOnly: false, size: 'sm' })
</script>

<template>
  <span class="inline-flex items-center gap-2">
    <svg viewBox="0 0 32 32" :class="size === 'md' ? 'h-8 w-8' : 'h-6 w-6'" class="shrink-0" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#2563eb" />
      <path fill="#fff" d="M8.5 8.5h11v3.3h-7.3v2.55h6.2v3.3h-6.2v2.55h7.3v3.3h-11z" />
      <path fill="#bfdbfe" d="M24 5.2l1.05 2.75 2.75 1.05-2.75 1.05L24 12.8l-1.05-2.75L20.2 9l2.75-1.05z" />
    </svg>
    <span v-if="!markOnly" class="font-semibold tracking-tight text-neutral-900 dark:text-neutral-100" :class="size === 'md' ? 'text-xl' : 'text-sm'">
      ERP<span class="text-blue-600 dark:text-blue-400">Intel</span>
    </span>
    <span v-else class="sr-only">ERPIntel</span>
  </span>
</template>
