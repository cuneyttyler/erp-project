import { defineStore } from 'pinia'
import { ref } from 'vue'

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
  // the message stays 'pending' until the user confirms or rejects it.
  pendingAction?: {
    description: string
    status: 'pending' | 'approved' | 'rejected'
  }
}

// Conversation state for the persistent AI side-panel (technical.md §10.2).
// Connects via the Channels WebSocket/SSE endpoint (technical.md §6) once
// apps/ai_core lands -- this store just holds client-side state for now.
export const useAIStore = defineStore('ai', () => {
  const isOpen = ref(false)
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)

  function toggle() {
    isOpen.value = !isOpen.value
  }

  function sendMessage(text: string) {
    messages.value.push({ id: crypto.randomUUID(), role: 'user', text })
    // Wired to the real streaming endpoint once it exists (technical.md §8.3).
  }

  return { isOpen, messages, isStreaming, toggle, sendMessage }
})
