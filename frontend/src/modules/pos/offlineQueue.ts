import { ref } from 'vue'

import type { CheckoutLineInput, CheckoutPaymentInput, usePOSStore } from '@/modules/pos/stores/pos'

/**
 * REQ-POS-008 / technical.md §10.6: the POS interface must remain operable
 * (queue-and-sync) during short internet outages. This is the "queue"
 * half -- a local IndexedDB store of not-yet-submitted sales, replayed once
 * connectivity returns. The service worker (public/pos-sw.js, registered in
 * main.ts) is the other half: it keeps the POS screen itself loadable while
 * offline. Both are deliberately scoped to POS only, not the whole app
 * (technical.md §10.6 -- the general ERP UI doesn't need this).
 *
 * Each queued sale carries the same `clientReference` that
 * `POSSale.client_reference` enforces uniqueness on server-side
 * (apps/pos/models.py) -- replaying a queued entry twice (e.g. the flush ran
 * again before IndexedDB deletion committed) is safe by construction, not
 * by careful sequencing here.
 */

const DB_NAME = 'pos-offline-queue'
const STORE_NAME = 'sales'
const DB_VERSION = 1

export interface QueuedSale {
  shiftId: number
  lines: CheckoutLineInput[]
  payments: CheckoutPaymentInput[]
  clientReference: string
  queuedAt: string
}

export const pendingOfflineCount = ref(0)
export const failedOfflineSales = ref<{ entry: QueuedSale; error: string }[]>([])

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'clientReference' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export function isOnline(): boolean {
  return navigator.onLine
}

export async function queueOfflineSale(entry: Omit<QueuedSale, 'queuedAt'>): Promise<void> {
  const db = await openDB()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).put({ ...entry, queuedAt: new Date().toISOString() })
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
  await refreshPendingCount()
}

async function getAllQueued(): Promise<QueuedSale[]> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const request = tx.objectStore(STORE_NAME).getAll()
    request.onsuccess = () => resolve(request.result as QueuedSale[])
    request.onerror = () => reject(request.error)
  })
}

async function removeQueued(clientReference: string): Promise<void> {
  const db = await openDB()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).delete(clientReference)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function refreshPendingCount(): Promise<void> {
  const all = await getAllQueued()
  pendingOfflineCount.value = all.length
}

let flushing = false

/** Replays every queued sale through the real store's checkout() action.
 * Stops (and keeps the remainder queued) on the first network-looking
 * failure -- connectivity may have dropped again mid-flush. A failure the
 * server actually rejected (e.g. stock sold out from another till in the
 * meantime) is instead pulled out of the queue and surfaced in
 * `failedOfflineSales` -- retrying it forever would never succeed, and
 * silently dropping it would lose a real sale a cashier already promised
 * a customer. */
export async function flushOfflineQueue(pos: ReturnType<typeof usePOSStore>): Promise<void> {
  if (flushing || !isOnline()) return
  flushing = true
  try {
    const queued = await getAllQueued()
    for (const entry of queued) {
      try {
        await pos.checkout(entry.shiftId, entry.lines, entry.payments, entry.clientReference)
        await removeQueued(entry.clientReference)
      } catch (e: any) {
        if (!e?.response) {
          break // network failure -- stop, leave the rest queued for next time
        }
        await removeQueued(entry.clientReference)
        failedOfflineSales.value.push({ entry, error: e.response?.data?.detail ?? 'Bilinmeyen hata' })
      }
    }
  } finally {
    await refreshPendingCount()
    flushing = false
  }
}
