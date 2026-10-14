import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'
import { i18n } from '@/shared/i18n'
import { useEntityStore } from '@/shared/stores/entity'

export interface Citation {
  label: string
  route: string
}

// The structured results the assistant's tools produce, rendered under its
// reply (shapes defined in backend apps/ai_core/tools.py).
export interface TableBlock {
  type: 'table'
  title: string
  resource: string
  columns: string[]
  rows: Record<string, unknown>[]
  total: number
}

export interface ChartBlock {
  type: 'chart'
  title: string
  // Set when the chart came from a named reporting series.
  series_name?: string
  chart: 'bar' | 'line' | 'hbar'
  format: 'money' | 'number'
  label_kind: 'month' | 'date' | 'text'
  series: { name: string; points: { label: string; value: string }[] }[]
}

export interface RecordBlock {
  type: 'record'
  resource: string
  id: string
  title: string
  fields: Record<string, unknown>
}

// A change the assistant has proposed (backend PendingApproval). Nothing
// has happened while it is `pending`: it runs only when a person approves
// it, as that person (REQ-CORE-AI-007).
export interface Proposal {
  id: number
  action_name: string
  resource: string
  operation: string
  target_id: string
  action_input: Record<string, unknown>
  preview: { target_label?: string; reason?: string; changes?: { field: string; before: unknown; after: unknown }[] }
  status: 'pending' | 'executed' | 'failed' | 'rejected'
  can_approve: boolean
  requested_by_username: string
  resolved_by_username: string | null
  result: Record<string, unknown> | null
  error: string
}

export interface ProposalBlock {
  type: 'proposal'
  approval: Proposal
}

export type Block = TableBlock | ChartBlock | RecordBlock | ProposalBlock

// What the assistant is doing mid-turn (the stream's `progress` events).
export interface ProgressStep {
  step: 'thinking' | 'tool'
  tool?: string
  kind?: string
  resource?: string
  operation?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  blocks: Block[]
  citations: Citation[]
}

export interface ConversationSummary {
  id: number
  title: string
  updated_at: string
}

interface ChatResponse {
  conversation: ConversationSummary | null
  reply: string
  blocks: Block[]
  citations: Citation[]
  configured: boolean
}

// The assistant page's state. Conversations live on the server (so they
// survive a reload and can be reopened); this store holds the list, the
// one that's open, and the turn in flight.
export const useAIStore = defineStore('ai', () => {
  const conversations = ref<ConversationSummary[]>([])
  const currentId = ref<number | null>(null)
  const messages = ref<ChatMessage[]>([])
  const isThinking = ref(false)
  const progress = ref<ProgressStep[]>([])
  const isLoadingConversation = ref(false)
  const configured = ref(true)

  async function fetchConversations() {
    const { data } = await apiClient.get<ConversationSummary[]>('ai/conversations/')
    conversations.value = data
  }

  function startNew() {
    currentId.value = null
    messages.value = []
  }

  async function open(id: number) {
    if (isThinking.value) return
    isLoadingConversation.value = true
    try {
      const { data } = await apiClient.get<ConversationSummary & { messages: (Omit<ChatMessage, 'id'> & { id: number })[] }>(`ai/conversations/${id}/`)
      currentId.value = id
      messages.value = data.messages.map((message) => ({ ...message, id: String(message.id) }))
    } finally {
      isLoadingConversation.value = false
    }
  }

  async function remove(id: number) {
    await apiClient.delete(`ai/conversations/${id}/`)
    conversations.value = conversations.value.filter((conversation) => conversation.id !== id)
    if (currentId.value === id) startNew()
  }

  // One turn over the streaming endpoint: progress events land in
  // `progress` as the assistant works, the final `done` event is the
  // response. (axios can't read a response body as it arrives; fetch can.)
  async function streamTurn(body: Record<string, unknown>): Promise<ChatResponse> {
    const csrf = document.cookie.split('; ').find((c) => c.startsWith('csrftoken='))?.slice('csrftoken='.length) ?? ''
    const response = await fetch(`${apiClient.defaults.baseURL}ai/chat/stream/`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf), 'Accept-Language': i18n.global.locale.value },
      body: JSON.stringify(body),
    })
    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`)
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
    let buffer = ''
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += value
      let end: number
      while ((end = buffer.indexOf('\n\n')) !== -1) {
        const chunk = buffer.slice(0, end)
        buffer = buffer.slice(end + 2)
        let event = 'message'
        let data = ''
        for (const line of chunk.split('\n')) {
          if (line.startsWith('event: ')) event = line.slice(7)
          else if (line.startsWith('data: ')) data += line.slice(6)
        }
        if (!data) continue // a comment line (": stream open")
        const payload = JSON.parse(data)
        if (event === 'progress') progress.value.push(payload)
        else if (event === 'done') return payload as ChatResponse
        else if (event === 'error') throw new Error(payload.detail)
      }
    }
    throw new Error('The stream ended without an answer.')
  }

  async function send(text: string) {
    messages.value.push({ id: crypto.randomUUID(), role: 'user', text, blocks: [], citations: [] })
    isThinking.value = true
    progress.value = []
    // The turn belongs to the conversation it was sent in, even if the
    // user opens another one before the answer arrives.
    const sentIn = currentId.value
    try {
      const data = await streamTurn({
        message: text,
        locale: i18n.global.locale.value,
        conversation_id: sentIn,
        entity: useEntityStore().currentEntityId,
      })
      configured.value = data.configured
      if (data.conversation) {
        const existing = conversations.value.findIndex((conversation) => conversation.id === data.conversation!.id)
        if (existing !== -1) conversations.value.splice(existing, 1)
        conversations.value.unshift(data.conversation)
      }
      if (currentId.value !== sentIn) return
      if (data.conversation) currentId.value = data.conversation.id
      messages.value.push({ id: crypto.randomUUID(), role: 'assistant', text: data.reply, blocks: data.blocks, citations: data.citations })
    } catch {
      if (currentId.value === sentIn) {
        messages.value.push({ id: crypto.randomUUID(), role: 'assistant', text: i18n.global.t('assistant.errors.send'), blocks: [], citations: [] })
      }
    } finally {
      isThinking.value = false
      progress.value = []
    }
  }

  // Approve or reject a proposal. The card updates in place with whatever
  // the server says happened -- including "it ran and was refused".
  async function resolve(proposal: Proposal, decision: 'approve' | 'reject'): Promise<string | null> {
    try {
      const { data } = await apiClient.post<Proposal>(`ai/pending-approvals/${proposal.id}/${decision}/`)
      Object.assign(proposal, data)
      return null
    } catch (e: any) {
      return e?.response?.data?.detail ?? i18n.global.t('assistant.errors.resolve')
    }
  }

  function reset() {
    conversations.value = []
    startNew()
  }

  return { conversations, currentId, messages, isThinking, progress, isLoadingConversation, configured, fetchConversations, startNew, open, remove, send, resolve, reset }
})
