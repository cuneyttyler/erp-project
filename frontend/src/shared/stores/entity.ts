import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export interface Entity {
  id: number
  name: string
  code: string
  currency: string
  is_active: boolean
}

const CURRENT_ENTITY_KEY = 'current-entity-id'

// REQ-CORE-ENT-001: which legal entity/company the user is currently
// working in. A single global selection (the header switcher in App.vue)
// rather than a per-screen picker -- every GL/AR/AP screen implicitly
// operates within whichever entity is "current" here, the same UX shape
// most multi-entity ERPs use. Tier-gating this to Professional+
// (product.md §7.2) isn't implemented yet -- active_packages only models
// per-package gating today, not subscription tier -- so this is available
// to every tenant for now; flagged in docs/notes.md, not hidden.
export const useEntityStore = defineStore('entity', () => {
  const entities = ref<Entity[]>([])
  const storedId = Number(localStorage.getItem(CURRENT_ENTITY_KEY))
  const currentEntityId = ref<number | null>(Number.isFinite(storedId) && storedId > 0 ? storedId : null)

  async function fetchEntities() {
    const { data } = await apiClient.get('core/entities/', { params: { page_size: 100 } })
    entities.value = data.results ?? data
    const stillValid = entities.value.some((e) => e.id === currentEntityId.value)
    if (!stillValid && entities.value.length > 0) {
      setCurrentEntity(entities.value[0].id)
    }
  }

  function setCurrentEntity(id: number) {
    currentEntityId.value = id
    localStorage.setItem(CURRENT_ENTITY_KEY, String(id))
  }

  async function createEntity(payload: { name: string; code: string; currency?: string }) {
    const { data } = await apiClient.post<Entity>('core/entities/', payload)
    entities.value.push(data)
    return data
  }

  return { entities, currentEntityId, fetchEntities, setCurrentEntity, createEntity }
})
