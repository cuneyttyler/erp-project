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
  // the message stays 'pending' until the user confirms or rejects it via
  // POST ai/pending-approvals/{id}/approve|reject/ (backend's
  // PendingApproval state machine, apps/ai_core/models.py).
  pendingAction?: {
    id: number
    description: string
    // Mirrors PendingApproval.STATUS_CHOICES (apps/ai_core/models.py)
    // exactly -- 'executed'/'failed' are both terminal outcomes of
    // approving, kept distinct so the UI can say if the action itself blew
    // up even though the approval step succeeded.
    status: 'pending' | 'executed' | 'failed' | 'rejected'
    resolving?: boolean
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
      const { data } = await apiClient.post<{
        reply: string
        citations: Citation[]
        configured: boolean
        pending_action: { id: number; description: string } | null
      }>('ai/chat/', { message: text, locale: i18n.global.locale.value, history })
      configured.value = data.configured
      messages.value.push({
        id: crypto.randomUUID(),
        role: 'assistant',
        text: data.reply,
        citations: data.citations,
        pendingAction: data.pending_action
          ? { id: data.pending_action.id, description: data.pending_action.description, status: 'pending' }
          : undefined,
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

  async function resolvePendingAction(approvalId: number, decision: 'approve' | 'reject') {
    const message = messages.value.find((m) => m.pendingAction?.id === approvalId)
    if (!message?.pendingAction || message.pendingAction.resolving) return
    message.pendingAction.resolving = true
    try {
      const { data } = await apiClient.post<{ status: 'executed' | 'failed' | 'rejected' }>(
        `ai/pending-approvals/${approvalId}/${decision}/`,
      )
      message.pendingAction.status = data.status
    } catch {
      // Leave it 'pending' -- the approve/reject buttons stay visible so the
      // user can retry, rather than silently losing the proposal.
    } finally {
      message.pendingAction.resolving = false
    }
  }

  function approvePendingAction(approvalId: number) {
    return resolvePendingAction(approvalId, 'approve')
  }

  function rejectPendingAction(approvalId: number) {
    return resolvePendingAction(approvalId, 'reject')
  }

  return {
    isOpen,
    messages,
    isStreaming,
    configured,
    toggle,
    sendMessage,
    approvePendingAction,
    rejectPendingAction,
  }
})
