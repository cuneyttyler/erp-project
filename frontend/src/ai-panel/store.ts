import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'
import { i18n } from '@/shared/i18n'

export interface Citation {
  label: string
  route: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  citations?: Citation[]
  // Set when the assistant is proposing a mutating action (REQ-AI-XCUT-003) --
  // the UI must render this distinctly from an already-completed action, and
  // the message stays 'pending' until the user confirms or rejects it. No
  // tool call sets this yet (the write/action path isn't built -- see
  // docs/notes.md); the field and its rendering in AIPanel.vue are kept so
  // that path is a backend addition later, not a UI rewrite.
  pendingAction?: {
    description: string
    status: 'pending' | 'approved' | 'rejected'
  }
}

// Conversation state for the persistent AI side-panel (technical.md §10.2).
// Calls the synchronous /api/v1/ai/chat/ endpoint (technical.md §8.3) --
// stateless server-side per docs/notes.md, so this store's own `messages`
// list IS the conversation's source of truth; each turn resends the prior
// history so the backend has context without persisting it itself.
export const useAIStore = defineStore('ai', () => {
  const isOpen = ref(false)
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const configured = ref(true)

  function toggle() {
    isOpen.value = !isOpen.value
  }

  async function sendMessage(text: string) {
    messages.value.push({ id: crypto.randomUUID(), role: 'user', text })
    isStreaming.value = true
    try {
      const history = messages.value
        .slice(0, -1)
        .map((m) => ({ role: m.role, content: m.text }))
      const { data } = await apiClient.post<{ reply: string; citations: Citation[]; configured: boolean }>(
        'ai/chat/',
        { message: text, locale: i18n.global.locale.value, history },
      )
      configured.value = data.configured
      messages.value.push({
        id: crypto.randomUUID(),
        role: 'assistant',
        text: data.reply,
        citations: data.citations,
      })
    } catch {
      messages.value.push({
        id: crypto.randomUUID(),
        role: 'assistant',
        text:
          i18n.global.locale.value === 'tr'
            ? 'Bir hata oluştu, lütfen tekrar deneyin.'
            : 'Something went wrong, please try again.',
      })
    } finally {
      isStreaming.value = false
    }
  }

  return { isOpen, messages, isStreaming, configured, toggle, sendMessage }
})
