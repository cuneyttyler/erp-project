import { defineStore } from 'pinia'
import { ref } from 'vue'

import { apiClient } from '@/shared/api/client'

export type Platform = 'shopify' | 'trendyol' | 'hepsiburada'

export interface MarketplaceAccount {
  id: number
  platform: Platform
  name: string
  entity: number
  entity_code: string
  warehouse: number
  warehouse_code: string
  shop_domain: string
  is_active: boolean
  last_synced_at: string | null
  created_at: string
}

export interface MarketplaceListing {
  id: number
  account: number
  item: number
  item_sku: string
  item_name: string
  external_sku: string
  external_variant_id: string
  external_location_id: string
  is_active: boolean
}

export type MarketplaceOrderStatus = 'new' | 'synced' | 'failed'

export interface MarketplaceOrder {
  id: number
  account: number
  account_name: string
  external_order_id: string
  status: MarketplaceOrderStatus
  sales_order: number | null
  error: string
  synced_at: string | null
  created_at: string
}

export interface SyncResult {
  created?: number
  skipped?: number
  failed: number
  pushed?: number
}

// E-commerce package state (REQ-ECOM-001/003) -- src/modules/ecommerce/, a
// real independently-priced Package (product.md §6.2, development-plan.md §6).
export const useEcommerceStore = defineStore('ecommerce', () => {
  const accounts = ref<MarketplaceAccount[]>([])
  const listings = ref<MarketplaceListing[]>([])
  const orders = ref<MarketplaceOrder[]>([])

  async function fetchAccounts() {
    const { data } = await apiClient.get('ecommerce/accounts/', { params: { page_size: 100 } })
    accounts.value = data.results ?? data
  }

  async function createAccount(payload: {
    platform: Platform
    name: string
    entity: number
    warehouse: number
    shop_domain: string
    api_key?: string
    api_secret?: string
  }) {
    const { data } = await apiClient.post<MarketplaceAccount>('ecommerce/accounts/', payload)
    accounts.value.unshift(data)
    return data
  }

  function replaceAccount(account: MarketplaceAccount) {
    const idx = accounts.value.findIndex((a) => a.id === account.id)
    if (idx !== -1) accounts.value[idx] = account
  }

  async function syncOrders(accountId: number) {
    const { data } = await apiClient.post<SyncResult>(`ecommerce/accounts/${accountId}/sync-orders/`)
    await fetchAccounts()
    return data
  }

  async function pushStock(accountId: number) {
    const { data } = await apiClient.post<SyncResult>(`ecommerce/accounts/${accountId}/push-stock/`)
    return data
  }

  async function fetchListings(accountId?: number) {
    const { data } = await apiClient.get('ecommerce/listings/', { params: { page_size: 200, account: accountId } })
    listings.value = data.results ?? data
  }

  async function createListing(payload: {
    account: number
    item: number
    external_sku: string
    external_variant_id?: string
    external_location_id?: string
  }) {
    const { data } = await apiClient.post<MarketplaceListing>('ecommerce/listings/', payload)
    listings.value.unshift(data)
    return data
  }

  async function fetchOrders(accountId?: number) {
    const { data } = await apiClient.get('ecommerce/orders/', { params: { page_size: 100, account: accountId } })
    orders.value = data.results ?? data
  }

  return {
    accounts,
    listings,
    orders,
    fetchAccounts,
    createAccount,
    replaceAccount,
    syncOrders,
    pushStock,
    fetchListings,
    createListing,
    fetchOrders,
  }
})
