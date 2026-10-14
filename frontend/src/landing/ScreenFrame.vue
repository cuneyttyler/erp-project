<script setup lang="ts">
// A product screenshot in a plain browser-window frame. The frame gives a
// light-coloured screenshot an edge on a light page and keeps it from
// glaring on a dark one.
defineProps<{ src: string; alt: string; eager?: boolean }>()
</script>

<template>
  <figure class="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-xl shadow-neutral-900/5 dark:border-neutral-700 dark:shadow-black/40">
    <div class="flex items-center gap-1.5 border-b border-neutral-200 bg-neutral-100 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-800" aria-hidden="true">
      <span class="h-2.5 w-2.5 rounded-full bg-neutral-300 dark:bg-neutral-600" />
      <span class="h-2.5 w-2.5 rounded-full bg-neutral-300 dark:bg-neutral-600" />
      <span class="h-2.5 w-2.5 rounded-full bg-neutral-300 dark:bg-neutral-600" />
    </div>
    <img :src="src" :alt="alt" :loading="eager ? 'eager' : 'lazy'" decoding="async" class="block h-auto w-full" />
  </figure>
</template>
