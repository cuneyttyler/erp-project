<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/shared/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch {
    error.value = 'Kullanıcı adı veya parola hatalı.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="flex h-full items-center justify-center bg-neutral-50 dark:bg-neutral-950">
    <form
      class="w-80 space-y-4 rounded-lg border border-neutral-200 bg-white p-6 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
      @submit.prevent="submit"
    >
      <h1 class="text-lg font-semibold text-neutral-900 dark:text-neutral-100">AI-Native ERP</h1>

      <div>
        <label class="mb-1 block text-sm text-neutral-600 dark:text-neutral-400">Kullanıcı Adı</label>
        <input
          v-model="username"
          type="text"
          required
          class="w-full rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-800"
        />
      </div>

      <div>
        <label class="mb-1 block text-sm text-neutral-600 dark:text-neutral-400">Parola</label>
        <input
          v-model="password"
          type="password"
          required
          class="w-full rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-800"
        />
      </div>

      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

      <button
        type="submit"
        :disabled="submitting"
        class="w-full rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        Giriş Yap
      </button>
    </form>
  </div>
</template>
