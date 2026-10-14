<script setup lang="ts">
import { LockClosedIcon, PencilSquareIcon, PlusIcon, ShieldCheckIcon, TrashIcon } from '@heroicons/vue/24/outline'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import ActionPicker from '@/core/access/ActionPicker.vue'
import { useActionLabels } from '@/core/access/labels'
import { apiErrorMessage, useAccessStore, type ManagedUser, type Permission, type Role } from '@/core/stores/access'
import AppModal from '@/shared/components/AppModal.vue'
import { useAuthStore } from '@/shared/stores/auth'

// User management (organization admins only). Four tabs that follow the
// chain a grant travels along, right to left: the Actions the app offers
// are bundled into Permissions, permissions into Roles, and roles are given
// to Users -- who can also be granted individual actions directly.
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useAccessStore()
const auth = useAuthStore()
const labels = useActionLabels()

type Tab = 'users' | 'roles' | 'permissions' | 'actions'
const TABS: Tab[] = ['users', 'roles', 'permissions', 'actions']
const tab = computed<Tab>(() => (TABS.includes(route.query.tab as Tab) ? (route.query.tab as Tab) : 'users'))
function setTab(next: Tab) {
  router.replace({ query: next === 'users' ? {} : { tab: next } })
}

const isLoading = ref(true)
const loadError = ref('')
onMounted(async () => {
  try {
    await store.fetchAll()
  } catch (e) {
    loadError.value = apiErrorMessage(e, t('access.errors.load'))
  } finally {
    isLoading.value = false
  }
})

const counts = computed<Record<Tab, number>>(() => ({
  users: store.users.length,
  roles: store.roles.length,
  permissions: store.permissions.length,
  actions: store.actionCount,
}))

const rolesById = computed(() => Object.fromEntries(store.roles.map((role) => [role.id, role])))
const permissionsById = computed(() => Object.fromEntries(store.permissions.map((permission) => [permission.id, permission])))
const customPermissions = computed(() => store.permissions.filter((permission) => !permission.is_system))
const builtInPermissions = computed(() => store.permissions.filter((permission) => permission.is_system))

function formatDateTime(iso: string | null): string {
  if (!iso) return t('access.users.neverLoggedIn')
  return new Intl.DateTimeFormat(locale.value === 'tr' ? 'tr-TR' : 'en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))
}

// One modal at a time; `form` is a scratch copy so cancelling changes nothing.
const editing = ref<null | 'user' | 'role' | 'permission'>(null)
const editingId = ref<number | undefined>()
const isSaving = ref(false)
const formError = ref('')

function open(kind: 'user' | 'role' | 'permission', id?: number) {
  editing.value = kind
  editingId.value = id
  formError.value = ''
}
function close() {
  editing.value = null
}

async function submit(save: () => Promise<unknown>) {
  formError.value = ''
  isSaving.value = true
  try {
    await save()
    close()
    // The admin may have just changed what they themselves can do.
    await auth.fetchMe()
  } catch (e) {
    formError.value = apiErrorMessage(e, t('access.errors.save'))
  } finally {
    isSaving.value = false
  }
}

// ------------------------------------------------------------------ users
const userForm = reactive({
  username: '',
  first_name: '',
  last_name: '',
  email: '',
  preferred_locale: 'tr' as 'tr' | 'en',
  is_active: true,
  password: '',
  role_ids: [] as number[],
  direct_actions: [] as string[],
})
const showDirectActions = ref(false)

function editUser(user?: ManagedUser) {
  Object.assign(userForm, {
    username: user?.username ?? '',
    first_name: user?.first_name ?? '',
    last_name: user?.last_name ?? '',
    email: user?.email ?? '',
    preferred_locale: user?.preferred_locale ?? 'tr',
    is_active: user?.is_active ?? true,
    password: '',
    role_ids: [...(user?.role_ids ?? [])],
    direct_actions: [...(user?.direct_actions ?? [])],
  })
  showDirectActions.value = (user?.direct_actions.length ?? 0) > 0
  open('user', user?.id)
}

function saveUser() {
  const { password, ...rest } = userForm
  // An empty password on an existing user means "leave it as it is".
  return submit(() => store.saveUser(password ? { ...rest, password } : rest, editingId.value))
}

function toggleRole(id: number) {
  userForm.role_ids = userForm.role_ids.includes(id) ? userForm.role_ids.filter((rid) => rid !== id) : [...userForm.role_ids, id]
}

// ------------------------------------------------------------------ roles
const roleForm = reactive({ name: '', description: '', permission_ids: [] as number[] })
const viewingRole = ref<Role | null>(null)

function editRole(role?: Role) {
  viewingRole.value = role?.is_system ? role : null
  Object.assign(roleForm, { name: role?.name ?? '', description: role?.description ?? '', permission_ids: [...(role?.permission_ids ?? [])] })
  open('role', role?.id)
}

function saveRole() {
  return submit(() => store.saveRole({ ...roleForm }, editingId.value))
}

function togglePermission(id: number) {
  roleForm.permission_ids = roleForm.permission_ids.includes(id) ? roleForm.permission_ids.filter((pid) => pid !== id) : [...roleForm.permission_ids, id]
}

// ------------------------------------------------------------ permissions
const permissionForm = reactive({ name: '', description: '', actions: [] as string[] })
const viewingPermission = ref<Permission | null>(null)

function editPermission(permission?: Permission) {
  viewingPermission.value = permission?.is_system ? permission : null
  Object.assign(permissionForm, { name: permission?.name ?? '', description: permission?.description ?? '', actions: [...(permission?.actions ?? [])] })
  open('permission', permission?.id)
}

function savePermission() {
  return submit(() => store.savePermission({ ...permissionForm }, editingId.value))
}

// ----------------------------------------------------------------- delete
const pendingDelete = ref<null | { kind: 'role' | 'permission'; id: number; name: string; usedBy: number }>(null)
const deleteError = ref('')

async function confirmDelete() {
  if (!pendingDelete.value) return
  deleteError.value = ''
  try {
    if (pendingDelete.value.kind === 'role') await store.deleteRole(pendingDelete.value.id)
    else await store.deletePermission(pendingDelete.value.id)
    pendingDelete.value = null
  } catch (e) {
    deleteError.value = apiErrorMessage(e, t('access.errors.delete'))
  }
}

const inputClass = 'w-full rounded border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900'
const labelClass = 'mb-1 block text-xs font-medium text-neutral-600 dark:text-neutral-400'
const primaryButton = 'rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50'
const secondaryButton =
  'rounded border border-neutral-300 bg-white px-3 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:bg-neutral-800'
const iconButton = 'rounded p-1.5 text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 dark:hover:bg-neutral-800 dark:hover:text-neutral-100'
const chip = 'rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300'
const th = 'px-4 py-2 text-left text-xs font-medium text-neutral-500'
const td = 'px-4 py-2.5 align-top text-sm text-neutral-800 dark:text-neutral-200'
</script>

<template>
  <section class="p-6 lg:p-8">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{{ t('access.title') }}</h1>
        <p class="mt-1 max-w-3xl text-sm text-neutral-500">{{ t('access.subtitle') }}</p>
      </div>
      <button v-if="tab === 'users'" :class="[primaryButton, 'flex items-center gap-1.5']" @click="editUser()">
        <PlusIcon class="h-4 w-4" />{{ t('access.users.new') }}
      </button>
      <button v-else-if="tab === 'roles'" :class="[primaryButton, 'flex items-center gap-1.5']" @click="editRole()">
        <PlusIcon class="h-4 w-4" />{{ t('access.roles.new') }}
      </button>
      <button v-else-if="tab === 'permissions'" :class="[primaryButton, 'flex items-center gap-1.5']" @click="editPermission()">
        <PlusIcon class="h-4 w-4" />{{ t('access.permissions.new') }}
      </button>
    </div>

    <div class="mt-5 flex gap-1 border-b border-neutral-200 dark:border-neutral-800" role="tablist">
      <button
        v-for="option in TABS"
        :key="option"
        role="tab"
        :aria-selected="tab === option"
        class="-mb-px border-b-2 px-3 py-2 text-sm font-medium"
        :class="tab === option ? 'border-blue-600 text-blue-700 dark:text-blue-400' : 'border-transparent text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200'"
        @click="setTab(option)"
      >
        {{ t(`access.tabs.${option}`) }}
        <span class="ml-1 text-xs font-normal text-neutral-400">{{ counts[option] }}</span>
      </button>
    </div>

    <p v-if="loadError" class="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300" role="alert">{{ loadError }}</p>
    <p v-else-if="isLoading" class="mt-8 text-sm text-neutral-500">{{ t('access.loading') }}</p>

    <template v-else>
      <!-- ============================================================ Users -->
      <div v-if="tab === 'users'" class="mt-4 overflow-x-auto rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
        <table class="w-full">
          <thead class="border-b border-neutral-200 dark:border-neutral-800">
            <tr>
              <th :class="th">{{ t('access.users.user') }}</th>
              <th :class="th">{{ t('access.users.roles') }}</th>
              <th :class="th">{{ t('access.users.status') }}</th>
              <th :class="th">{{ t('access.users.lastLogin') }}</th>
              <th :class="th" />
            </tr>
          </thead>
          <tbody class="divide-y divide-neutral-100 dark:divide-neutral-800">
            <tr v-for="user in store.users" :key="user.id">
              <td :class="td">
                <p class="font-medium">{{ user.full_name || user.username }}</p>
                <p class="text-xs text-neutral-500">{{ user.username }}<template v-if="user.email"> · {{ user.email }}</template></p>
              </td>
              <td :class="td">
                <div class="flex flex-wrap gap-1">
                  <span v-if="user.is_org_admin" class="flex items-center gap-1 rounded bg-blue-50 px-1.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                    <ShieldCheckIcon class="h-3.5 w-3.5" />{{ t('access.users.admin') }}
                  </span>
                  <template v-for="roleId in user.role_ids" :key="roleId">
                    <span v-if="rolesById[roleId] && !rolesById[roleId].grants_all" :class="chip">{{ labels.systemName(rolesById[roleId]) }}</span>
                  </template>
                  <span v-if="user.direct_actions.length" :class="chip">{{ t('access.users.directCount', { count: user.direct_actions.length }, user.direct_actions.length) }}</span>
                  <span v-if="!user.is_org_admin && !user.role_ids.length && !user.direct_actions.length" class="text-xs text-neutral-500">{{ t('access.users.noAccess') }}</span>
                </div>
              </td>
              <td :class="td">
                <span class="flex items-center gap-1.5 text-xs">
                  <span class="h-1.5 w-1.5 rounded-full" :class="user.is_active ? 'bg-green-600' : 'bg-neutral-400'" />
                  {{ user.is_active ? t('access.users.active') : t('access.users.inactive') }}
                </span>
              </td>
              <td :class="[td, 'whitespace-nowrap text-xs text-neutral-500']">{{ formatDateTime(user.last_login) }}</td>
              <td :class="[td, 'text-right']">
                <button :class="iconButton" :aria-label="t('access.actions.edit')" :title="t('access.actions.edit')" @click="editUser(user)"><PencilSquareIcon class="h-4 w-4" /></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ============================================================ Roles -->
      <div v-else-if="tab === 'roles'" class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
        <article v-for="role in store.roles" :key="role.id" class="flex flex-col rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h3 class="flex items-center gap-1.5 text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                {{ labels.systemName(role) }}
                <LockClosedIcon v-if="role.is_system" class="h-3.5 w-3.5 text-neutral-400" :title="t('access.builtIn')" />
              </h3>
              <p class="mt-0.5 text-sm text-neutral-500">{{ role.is_system ? t(`access.systemRoleDescriptions.${role.system_key}`) : role.description }}</p>
            </div>
            <div class="flex shrink-0">
              <button :class="iconButton" :aria-label="role.is_system ? t('access.actions.view') : t('access.actions.edit')" :title="role.is_system ? t('access.actions.view') : t('access.actions.edit')" @click="editRole(role)">
                <PencilSquareIcon class="h-4 w-4" />
              </button>
              <button
                v-if="!role.is_system"
                :class="iconButton"
                :aria-label="t('access.actions.delete')"
                :title="t('access.actions.delete')"
                @click="pendingDelete = { kind: 'role', id: role.id, name: role.name, usedBy: role.user_count }"
              >
                <TrashIcon class="h-4 w-4" />
              </button>
            </div>
          </div>
          <div class="mt-3 flex flex-wrap gap-1">
            <span v-if="role.grants_all" class="rounded bg-blue-50 px-1.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300">{{ t('access.roles.everything') }}</span>
            <template v-for="permissionId in role.permission_ids" :key="permissionId">
              <span v-if="permissionsById[permissionId]" :class="chip">{{ labels.systemName(permissionsById[permissionId]) }}</span>
            </template>
            <span v-if="!role.grants_all && !role.permission_ids.length" class="text-xs text-neutral-500">{{ t('access.roles.noPermissions') }}</span>
          </div>
          <p class="mt-auto pt-3 text-xs text-neutral-500">{{ t('access.roles.userCount', { count: role.user_count }, role.user_count) }}</p>
        </article>
      </div>

      <!-- ====================================================== Permissions -->
      <div v-else-if="tab === 'permissions'">
        <template v-for="section in [{ id: 'custom', items: customPermissions }, { id: 'builtIn', items: builtInPermissions }]" :key="section.id">
          <h2 class="mt-6 text-xs font-semibold uppercase tracking-wide text-neutral-500">{{ t(`access.permissions.${section.id}`) }}</h2>
          <p v-if="section.id === 'builtIn'" class="mt-1 max-w-3xl text-xs text-neutral-500">{{ t('access.permissions.builtInNote') }}</p>
          <p v-if="section.items.length === 0" class="mt-3 rounded-lg border border-dashed border-neutral-300 p-6 text-center text-sm text-neutral-500 dark:border-neutral-700">
            {{ t('access.permissions.noneYet') }}
          </p>
          <div v-else class="mt-3 overflow-x-auto rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
            <table class="w-full">
              <thead class="border-b border-neutral-200 dark:border-neutral-800">
                <tr>
                  <th :class="th">{{ t('access.permissions.name') }}</th>
                  <th :class="th">{{ t('access.permissions.actions') }}</th>
                  <th :class="th">{{ t('access.permissions.usedIn') }}</th>
                  <th :class="th" />
                </tr>
              </thead>
              <tbody class="divide-y divide-neutral-100 dark:divide-neutral-800">
                <tr v-for="permission in section.items" :key="permission.id">
                  <td :class="td">
                    <p class="font-medium">{{ labels.systemName(permission) }}</p>
                    <p v-if="permission.description" class="text-xs text-neutral-500">{{ permission.description }}</p>
                  </td>
                  <td :class="[td, 'whitespace-nowrap']">{{ t('access.permissions.actionCount', { count: permission.actions.length }, permission.actions.length) }}</td>
                  <td :class="[td, 'whitespace-nowrap']">{{ t('access.permissions.roleCount', { count: permission.role_count }, permission.role_count) }}</td>
                  <td :class="[td, 'whitespace-nowrap text-right']">
                    <button :class="iconButton" :aria-label="permission.is_system ? t('access.actions.view') : t('access.actions.edit')" :title="permission.is_system ? t('access.actions.view') : t('access.actions.edit')" @click="editPermission(permission)">
                      <PencilSquareIcon class="h-4 w-4" />
                    </button>
                    <button
                      v-if="!permission.is_system"
                      :class="iconButton"
                      :aria-label="t('access.actions.delete')"
                      :title="t('access.actions.delete')"
                      @click="pendingDelete = { kind: 'permission', id: permission.id, name: permission.name, usedBy: permission.role_count }"
                    >
                      <TrashIcon class="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>

      <!-- ========================================================== Actions -->
      <div v-else class="mt-4">
        <p class="mb-3 max-w-3xl text-sm text-neutral-600 dark:text-neutral-400">{{ t('access.actionsIntro') }}</p>
        <ActionPicker :catalog="store.catalog" :model-value="[]" readonly />
      </div>
    </template>

    <!-- ============================================================ User form -->
    <AppModal v-if="editing === 'user'" :title="editingId ? t('access.users.edit') : t('access.users.new')" wide @close="close">
      <form id="user-form" class="space-y-4" @submit.prevent="saveUser">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label><span :class="labelClass">{{ t('access.users.username') }}</span><input v-model="userForm.username" required autocomplete="off" :class="inputClass" /></label>
          <label><span :class="labelClass">{{ t('access.users.email') }}</span><input v-model="userForm.email" type="email" autocomplete="off" :class="inputClass" /></label>
          <label><span :class="labelClass">{{ t('access.users.firstName') }}</span><input v-model="userForm.first_name" :class="inputClass" /></label>
          <label><span :class="labelClass">{{ t('access.users.lastName') }}</span><input v-model="userForm.last_name" :class="inputClass" /></label>
          <label>
            <span :class="labelClass">{{ editingId ? t('access.users.newPassword') : t('access.users.password') }}</span>
            <input v-model="userForm.password" type="password" autocomplete="new-password" :required="!editingId" :placeholder="editingId ? t('access.users.passwordUnchanged') : ''" :class="inputClass" />
          </label>
          <label>
            <span :class="labelClass">{{ t('access.users.language') }}</span>
            <select v-model="userForm.preferred_locale" :class="inputClass">
              <option value="tr">Türkçe</option>
              <option value="en">English</option>
            </select>
          </label>
        </div>
        <label class="flex items-center gap-2 text-sm text-neutral-800 dark:text-neutral-200">
          <input v-model="userForm.is_active" type="checkbox" class="h-4 w-4 rounded border-neutral-300" />
          {{ t('access.users.canSignIn') }}
        </label>

        <fieldset>
          <legend :class="labelClass">{{ t('access.users.roles') }}</legend>
          <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <label
              v-for="role in store.roles"
              :key="role.id"
              class="flex cursor-pointer items-start gap-2 rounded border border-neutral-200 p-2.5 text-sm dark:border-neutral-800"
              :class="userForm.role_ids.includes(role.id) ? 'border-blue-400 bg-blue-50 dark:border-blue-700 dark:bg-blue-950/40' : ''"
            >
              <input type="checkbox" class="mt-0.5 h-4 w-4 rounded border-neutral-300" :checked="userForm.role_ids.includes(role.id)" @change="toggleRole(role.id)" />
              <span>
                <span class="font-medium text-neutral-900 dark:text-neutral-100">{{ labels.systemName(role) }}</span>
                <span class="block text-xs text-neutral-500">{{ role.is_system ? t(`access.systemRoleDescriptions.${role.system_key}`) : role.description }}</span>
              </span>
            </label>
          </div>
        </fieldset>

        <div>
          <button type="button" class="text-sm font-medium text-blue-700 hover:underline dark:text-blue-400" @click="showDirectActions = !showDirectActions">
            {{ t('access.users.directActions') }} ({{ userForm.direct_actions.length }})
          </button>
          <p class="mt-0.5 text-xs text-neutral-500">{{ t('access.users.directActionsHint') }}</p>
          <ActionPicker v-if="showDirectActions" v-model="userForm.direct_actions" :catalog="store.catalog" class="mt-3" />
        </div>
        <p v-if="formError" class="text-sm text-red-600 dark:text-red-400" role="alert">{{ formError }}</p>
      </form>
      <template #footer>
        <button :class="secondaryButton" @click="close">{{ t('access.actions.cancel') }}</button>
        <button type="submit" form="user-form" :class="primaryButton" :disabled="isSaving">{{ t('access.actions.save') }}</button>
      </template>
    </AppModal>

    <!-- ============================================================ Role form -->
    <AppModal v-if="editing === 'role'" :title="viewingRole ? labels.systemName(viewingRole) : editingId ? t('access.roles.edit') : t('access.roles.new')" wide @close="close">
      <form id="role-form" class="space-y-4" @submit.prevent="saveRole">
        <p v-if="viewingRole" class="flex items-center gap-2 rounded border border-neutral-200 px-3 py-2 text-sm text-neutral-600 dark:border-neutral-800 dark:text-neutral-400">
          <LockClosedIcon class="h-4 w-4 shrink-0" />{{ t('access.builtInNote') }}
        </p>
        <template v-else>
          <label class="block"><span :class="labelClass">{{ t('access.roles.name') }}</span><input v-model="roleForm.name" required :class="inputClass" /></label>
          <label class="block"><span :class="labelClass">{{ t('access.roles.description') }}</span><input v-model="roleForm.description" :class="inputClass" /></label>
        </template>

        <p v-if="viewingRole?.grants_all" class="text-sm text-neutral-700 dark:text-neutral-300">{{ t('access.roles.everythingNote') }}</p>
        <template v-else>
          <fieldset v-for="section in [{ id: 'custom', items: customPermissions }, { id: 'builtIn', items: builtInPermissions }]" :key="section.id">
            <legend v-if="section.items.length" :class="labelClass">{{ t(`access.permissions.${section.id}`) }}</legend>
            <div class="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              <label v-for="permission in section.items" :key="permission.id" class="flex items-center gap-2 text-sm text-neutral-800 dark:text-neutral-200" :class="viewingRole ? '' : 'cursor-pointer'">
                <input type="checkbox" class="h-4 w-4 rounded border-neutral-300" :disabled="!!viewingRole" :checked="roleForm.permission_ids.includes(permission.id)" @change="togglePermission(permission.id)" />
                {{ labels.systemName(permission) }}
                <span class="text-xs text-neutral-500">({{ permission.actions.length }})</span>
              </label>
            </div>
          </fieldset>
        </template>
        <p v-if="formError" class="text-sm text-red-600 dark:text-red-400" role="alert">{{ formError }}</p>
      </form>
      <template #footer>
        <button :class="secondaryButton" @click="close">{{ viewingRole ? t('access.actions.close') : t('access.actions.cancel') }}</button>
        <button v-if="!viewingRole" type="submit" form="role-form" :class="primaryButton" :disabled="isSaving">{{ t('access.actions.save') }}</button>
      </template>
    </AppModal>

    <!-- ====================================================== Permission form -->
    <AppModal
      v-if="editing === 'permission'"
      :title="viewingPermission ? labels.systemName(viewingPermission) : editingId ? t('access.permissions.edit') : t('access.permissions.new')"
      wide
      @close="close"
    >
      <form id="permission-form" class="space-y-4" @submit.prevent="savePermission">
        <p v-if="viewingPermission" class="flex items-center gap-2 rounded border border-neutral-200 px-3 py-2 text-sm text-neutral-600 dark:border-neutral-800 dark:text-neutral-400">
          <LockClosedIcon class="h-4 w-4 shrink-0" />{{ t('access.builtInNote') }}
        </p>
        <template v-else>
          <label class="block"><span :class="labelClass">{{ t('access.permissions.name') }}</span><input v-model="permissionForm.name" required :class="inputClass" /></label>
          <label class="block"><span :class="labelClass">{{ t('access.permissions.description') }}</span><input v-model="permissionForm.description" :class="inputClass" /></label>
        </template>

        <div v-if="viewingPermission" class="flex flex-wrap gap-1.5">
          <span v-for="code in viewingPermission.actions" :key="code" :class="chip" :title="code">{{ labels.action(code) }}</span>
        </div>
        <ActionPicker v-else v-model="permissionForm.actions" :catalog="store.catalog" />
        <p v-if="formError" class="text-sm text-red-600 dark:text-red-400" role="alert">{{ formError }}</p>
      </form>
      <template #footer>
        <button :class="secondaryButton" @click="close">{{ viewingPermission ? t('access.actions.close') : t('access.actions.cancel') }}</button>
        <button v-if="!viewingPermission" type="submit" form="permission-form" :class="primaryButton" :disabled="isSaving">{{ t('access.actions.save') }}</button>
      </template>
    </AppModal>

    <!-- ======================================================= Delete confirm -->
    <AppModal v-if="pendingDelete" :title="t(`access.delete.${pendingDelete.kind}Title`)" @close="pendingDelete = null">
      <p class="text-sm text-neutral-700 dark:text-neutral-300">
        {{ t(`access.delete.${pendingDelete.kind}Body`, { name: pendingDelete.name, count: pendingDelete.usedBy }, pendingDelete.usedBy) }}
      </p>
      <p v-if="deleteError" class="mt-3 text-sm text-red-600 dark:text-red-400" role="alert">{{ deleteError }}</p>
      <template #footer>
        <button :class="secondaryButton" @click="pendingDelete = null">{{ t('access.actions.cancel') }}</button>
        <button class="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700" @click="confirmDelete">{{ t('access.actions.delete') }}</button>
      </template>
    </AppModal>
  </section>
</template>
