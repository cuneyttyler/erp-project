<script setup lang="ts">
import {
  ArchiveBoxIcon,
  BanknotesIcon,
  BookOpenIcon,
  BuildingOffice2Icon,
  CheckCircleIcon,
  CheckIcon,
  ClipboardDocumentCheckIcon,
  ClockIcon,
  CogIcon,
  ComputerDesktopIcon,
  CubeIcon,
  GlobeAltIcon,
  PresentationChartLineIcon,
  PuzzlePieceIcon,
  ShieldCheckIcon,
  ShoppingCartIcon,
  SparklesIcon,
  UserGroupIcon,
  UserPlusIcon,
} from '@heroicons/vue/24/outline'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import AppLogo from '@/shared/components/AppLogo.vue'
import { setLocale } from '@/shared/i18n'

import ScreenFrame from './ScreenFrame.vue'
import assistantEn from './images/assistant-en.webp'
import assistantTr from './images/assistant-tr.webp'
import auditEn from './images/audit-en.webp'
import auditTr from './images/audit-tr.webp'
import panelEn from './images/panel-en.webp'
import panelTr from './images/panel-tr.webp'
import pluginsEn from './images/plugins-en.webp'
import pluginsTr from './images/plugins-tr.webp'

// The public homepage: what ERPIntel is, what it does today, the plans, and
// what's still to come. It is the only page a visitor sees without signing
// in, and it brings its own layout (the route is `bare` -- see App.vue).
//
// Everything said here is meant to be true of the product as it is: the
// "Available today" list is what's built, and anything that isn't
// (e-documents, migration connectors, agents) is under "Coming next". Keep
// it that way when either list changes.
//
// The screenshots are of the real application with sample data, one set per
// language (see ./images/README.md for how they're regenerated).
const { t, tm, rt, locale } = useI18n()

const images = computed(() =>
  locale.value === 'tr'
    ? { panel: panelTr, assistant: assistantTr, audit: auditTr, plugins: pluginsTr }
    : { panel: panelEn, assistant: assistantEn, audit: auditEn, plugins: pluginsEn },
)

const sections = ['modules', 'assistant', 'control', 'plans', 'roadmap', 'faq'] as const

// One card per plugin, in the app's own order -- twelve, matching the
// "12 plugins" figure above.
const modules = [
  { key: 'companies', icon: BuildingOffice2Icon },
  { key: 'ledger', icon: BookOpenIcon },
  { key: 'receivables', icon: BanknotesIcon },
  { key: 'catalog', icon: CubeIcon },
  { key: 'inventory', icon: ArchiveBoxIcon },
  { key: 'purchasing', icon: ShoppingCartIcon },
  { key: 'sales', icon: UserPlusIcon },
  { key: 'manufacturing', icon: CogIcon },
  { key: 'hr', icon: UserGroupIcon },
  { key: 'pos', icon: ComputerDesktopIcon },
  { key: 'ecommerce', icon: GlobeAltIcon },
  { key: 'bi', icon: PresentationChartLineIcon },
]

// List-shaped copy lives in the locale files as arrays; `tm` returns the raw
// message tree and `rt` renders each string in it.
interface Titled {
  title: string
  body: string
}
interface Tier {
  name: string
  audience: string
  price: string
  features: string[]
}
const facts = computed(() => tm('landing.facts') as { value: string; label: string }[])
const assistantPoints = computed(() => tm('landing.assistant.points') as Titled[])
const assistantExamples = computed(() => tm('landing.assistant.examples') as string[])
const safetySteps = computed(() => tm('landing.safety.steps') as Titled[])
const tiers = computed(() => tm('landing.plans.tiers') as Tier[])
const todayItems = computed(() => tm('landing.roadmap.today.items') as string[])
const nextItems = computed(() => tm('landing.roadmap.next.items') as string[])
const faqItems = computed(() => tm('landing.faq.items') as { q: string; a: string }[])

// The plan most companies in the target range land on (15-75 people).
const HIGHLIGHTED_TIER = 1
const year = new Date().getFullYear()

const container = 'mx-auto w-full max-w-6xl px-5 sm:px-8'
// Side-by-side sections give the screenshot the wider column: it's a full
// application screen and needs the room to stay legible.
const textThenImage = 'lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]'
const imageThenText = 'lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]'
const eyebrow = 'text-sm font-semibold uppercase tracking-wide text-blue-700 dark:text-blue-400'
const heading = 'mt-2 text-3xl font-semibold tracking-tight text-neutral-900 sm:text-4xl dark:text-neutral-50'
const lead = 'mt-4 text-lg text-neutral-600 dark:text-neutral-400'
const primaryButton = 'inline-flex items-center justify-center rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700'
const secondaryButton =
  'inline-flex items-center justify-center rounded-lg border border-neutral-300 bg-white px-5 py-2.5 text-sm font-semibold text-neutral-800 hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800'
</script>

<template>
  <div class="text-neutral-800 dark:text-neutral-200">
    <!-- ================================================================ Nav -->
    <header class="sticky top-0 z-30 border-b border-neutral-200/80 bg-white/85 backdrop-blur dark:border-neutral-800/80 dark:bg-neutral-950/85">
      <div :class="[container, 'flex h-16 items-center justify-between gap-4']">
        <a href="#top" aria-label="ERPIntel"><AppLogo size="md" /></a>
        <nav class="hidden items-center gap-6 lg:flex" aria-label="Sections">
          <a
            v-for="section in sections"
            :key="section"
            :href="`#${section}`"
            class="text-sm font-medium text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-100"
          >
            {{ t(`landing.nav.${section}`) }}
          </a>
        </nav>
        <div class="flex items-center gap-3">
          <div class="flex rounded-lg border border-neutral-300 p-0.5 text-xs font-semibold dark:border-neutral-700" role="group" aria-label="Language">
            <button
              v-for="option in ['tr', 'en'] as const"
              :key="option"
              class="rounded-md px-2 py-1 uppercase"
              :class="locale === option ? 'bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900' : 'text-neutral-600 dark:text-neutral-400'"
              :aria-pressed="locale === option"
              @click="setLocale(option)"
            >
              {{ option }}
            </button>
          </div>
          <RouterLink :to="{ name: 'login' }" :class="[primaryButton, '!px-4 !py-2']">{{ t('landing.nav.signIn') }}</RouterLink>
        </div>
      </div>
    </header>

    <main id="top">
      <!-- ============================================================= Hero -->
      <section class="relative overflow-hidden border-b border-neutral-200 bg-gradient-to-b from-blue-50 via-white to-white dark:border-neutral-800 dark:from-blue-950/40 dark:via-neutral-950 dark:to-neutral-950">
        <div :class="[container, 'pb-16 pt-16 sm:pt-24']">
          <div class="mx-auto max-w-3xl text-center">
            <p :class="eyebrow">{{ t('landing.hero.eyebrow') }}</p>
            <h1 class="mt-3 text-4xl font-semibold tracking-tight text-neutral-900 sm:text-5xl sm:leading-[1.1] dark:text-neutral-50">
              {{ t('landing.hero.title') }}
            </h1>
            <p class="mt-5 text-lg text-neutral-600 sm:text-xl dark:text-neutral-400">{{ t('landing.hero.body') }}</p>
            <div class="mt-8 flex flex-wrap items-center justify-center gap-3">
              <RouterLink :to="{ name: 'login' }" :class="primaryButton">{{ t('landing.hero.primary') }}</RouterLink>
              <a href="#plans" :class="secondaryButton">{{ t('landing.hero.secondary') }}</a>
            </div>
          </div>
          <ScreenFrame class="mx-auto mt-14 max-w-5xl" :src="images.panel" :alt="t('landing.hero.imageAlt')" eager />
          <p class="mt-3 text-center text-xs text-neutral-500">{{ t('landing.hero.imageNote') }}</p>
        </div>
      </section>

      <!-- ============================================================ Facts -->
      <section class="border-b border-neutral-200 dark:border-neutral-800">
        <dl :class="[container, 'grid grid-cols-2 gap-y-8 py-10 lg:grid-cols-4']">
          <div v-for="fact in facts" :key="rt(fact.label)" class="px-2 text-center">
            <dt class="sr-only">{{ rt(fact.label) }}</dt>
            <dd class="text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">{{ rt(fact.value) }}</dd>
            <dd class="mt-1 text-sm text-neutral-600 dark:text-neutral-400">{{ rt(fact.label) }}</dd>
          </div>
        </dl>
      </section>

      <!-- ========================================================== Modules -->
      <section id="modules" class="scroll-mt-16 py-20">
        <div :class="container">
          <div class="max-w-3xl">
            <p :class="eyebrow">{{ t('landing.nav.modules') }}</p>
            <h2 :class="heading">{{ t('landing.modules.title') }}</h2>
            <p :class="lead">{{ t('landing.modules.body') }}</p>
          </div>
          <ul class="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <li
              v-for="module in modules"
              :key="module.key"
              class="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900"
            >
              <span class="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                <component :is="module.icon" class="h-5 w-5" />
              </span>
              <h3 class="mt-4 text-base font-semibold text-neutral-900 dark:text-neutral-100">{{ t(`landing.modules.items.${module.key}.title`) }}</h3>
              <p class="mt-1.5 text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">{{ t(`landing.modules.items.${module.key}.body`) }}</p>
            </li>
          </ul>
        </div>
      </section>

      <!-- ======================================================== Assistant -->
      <section id="assistant" class="scroll-mt-16 border-y border-neutral-200 bg-neutral-50 py-20 dark:border-neutral-800 dark:bg-neutral-900/40">
        <div :class="[container, 'grid grid-cols-1 items-center gap-12', textThenImage]">
          <div>
            <p :class="[eyebrow, 'flex items-center gap-1.5']"><SparklesIcon class="h-4 w-4" />{{ t('landing.assistant.eyebrow') }}</p>
            <h2 :class="heading">{{ t('landing.assistant.title') }}</h2>
            <p :class="lead">{{ t('landing.assistant.body') }}</p>
            <ul class="mt-8 space-y-6">
              <li v-for="point in assistantPoints" :key="rt(point.title)" class="flex gap-3">
                <CheckCircleIcon class="mt-0.5 h-6 w-6 shrink-0 text-blue-600 dark:text-blue-400" />
                <div>
                  <h3 class="font-semibold text-neutral-900 dark:text-neutral-100">{{ rt(point.title) }}</h3>
                  <p class="mt-1 text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">{{ rt(point.body) }}</p>
                </div>
              </li>
            </ul>
            <p class="mt-8 text-sm font-medium text-neutral-500">{{ t('landing.assistant.examplesTitle') }}</p>
            <ul class="mt-3 flex flex-wrap gap-2">
              <li
                v-for="example in assistantExamples"
                :key="rt(example)"
                class="rounded-full border border-neutral-300 bg-white px-3 py-1.5 text-sm text-neutral-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300"
              >
                {{ rt(example) }}
              </li>
            </ul>
          </div>
          <ScreenFrame :src="images.assistant" :alt="t('landing.assistant.imageAlt')" />
        </div>
      </section>

      <!-- ========================================================== Control -->
      <section id="control" class="scroll-mt-16 py-20">
        <div :class="container">
          <div class="max-w-3xl">
            <p :class="eyebrow">{{ t('landing.control.eyebrow') }}</p>
            <h2 :class="heading">{{ t('landing.control.title') }}</h2>
          </div>

          <div class="mt-14 grid grid-cols-1 items-center gap-12" :class="imageThenText">
            <ScreenFrame :src="images.audit" :alt="t('landing.control.audit.imageAlt')" />
            <div class="space-y-10">
              <div class="flex gap-4">
                <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                  <ClipboardDocumentCheckIcon class="h-5 w-5" />
                </span>
                <div>
                  <h3 class="text-lg font-semibold text-neutral-900 dark:text-neutral-100">{{ t('landing.control.audit.title') }}</h3>
                  <p class="mt-1.5 leading-relaxed text-neutral-600 dark:text-neutral-400">{{ t('landing.control.audit.body') }}</p>
                </div>
              </div>
              <div class="flex gap-4">
                <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                  <ShieldCheckIcon class="h-5 w-5" />
                </span>
                <div>
                  <h3 class="text-lg font-semibold text-neutral-900 dark:text-neutral-100">{{ t('landing.control.permissions.title') }}</h3>
                  <p class="mt-1.5 leading-relaxed text-neutral-600 dark:text-neutral-400">{{ t('landing.control.permissions.body') }}</p>
                </div>
              </div>
            </div>
          </div>

          <div class="mt-20 grid grid-cols-1 items-center gap-12" :class="textThenImage">
            <div class="flex gap-4 lg:order-1">
              <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                <PuzzlePieceIcon class="h-5 w-5" />
              </span>
              <div>
                <h3 class="text-lg font-semibold text-neutral-900 dark:text-neutral-100">{{ t('landing.control.plugins.title') }}</h3>
                <p class="mt-1.5 leading-relaxed text-neutral-600 dark:text-neutral-400">{{ t('landing.control.plugins.body') }}</p>
              </div>
            </div>
            <ScreenFrame class="lg:order-2" :src="images.plugins" :alt="t('landing.control.plugins.imageAlt')" />
          </div>
        </div>
      </section>

      <!-- =========================================================== Safety -->
      <section class="border-y border-neutral-200 bg-neutral-50 py-20 dark:border-neutral-800 dark:bg-neutral-900/40">
        <div :class="container">
          <h2 :class="[heading, 'mt-0 max-w-3xl']">{{ t('landing.safety.title') }}</h2>
          <ol class="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <li v-for="(step, index) in safetySteps" :key="rt(step.title)" class="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
              <span class="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-sm font-semibold text-white">{{ index + 1 }}</span>
              <h3 class="mt-4 font-semibold text-neutral-900 dark:text-neutral-100">{{ rt(step.title) }}</h3>
              <p class="mt-1.5 text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">{{ rt(step.body) }}</p>
            </li>
          </ol>
        </div>
      </section>

      <!-- ============================================================ Plans -->
      <section id="plans" class="scroll-mt-16 py-20">
        <div :class="container">
          <div class="mx-auto max-w-3xl text-center">
            <p :class="eyebrow">{{ t('landing.plans.eyebrow') }}</p>
            <h2 :class="heading">{{ t('landing.plans.title') }}</h2>
            <p :class="lead">{{ t('landing.plans.body') }}</p>
          </div>
          <ul class="mt-12 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
            <li
              v-for="(tier, index) in tiers"
              :key="rt(tier.name)"
              class="relative flex flex-col rounded-xl border bg-white p-6 dark:bg-neutral-900"
              :class="index === HIGHLIGHTED_TIER ? 'border-blue-600 shadow-lg ring-1 ring-blue-600' : 'border-neutral-200 dark:border-neutral-800'"
            >
              <span v-if="index === HIGHLIGHTED_TIER" class="absolute -top-3 left-6 rounded-full bg-blue-600 px-2.5 py-0.5 text-xs font-semibold text-white">
                {{ t('landing.plans.popular') }}
              </span>
              <h3 class="text-lg font-semibold text-neutral-900 dark:text-neutral-100">{{ rt(tier.name) }}</h3>
              <p class="mt-1 text-sm text-neutral-600 dark:text-neutral-400">{{ rt(tier.audience) }}</p>
              <p class="mt-5 text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">{{ rt(tier.price) }}</p>
              <!-- The last tier is quoted, not priced per user. -->
              <p class="mt-1 h-5 text-sm text-neutral-500">{{ index < tiers.length - 1 ? t('landing.plans.perUser') : '' }}</p>
              <ul class="mt-6 space-y-3 border-t border-neutral-200 pt-6 text-sm dark:border-neutral-800">
                <li v-for="feature in tier.features" :key="rt(feature)" class="flex gap-2.5">
                  <CheckIcon class="mt-0.5 h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" />
                  <span class="text-neutral-700 dark:text-neutral-300">{{ rt(feature) }}</span>
                </li>
              </ul>
            </li>
          </ul>
          <p class="mt-8 text-center text-sm text-neutral-600 dark:text-neutral-400">{{ t('landing.plans.addOn') }}</p>
          <p class="mt-2 text-center text-xs text-neutral-500">{{ t('landing.plans.indicative') }}</p>
        </div>
      </section>

      <!-- ========================================================== Roadmap -->
      <section id="roadmap" class="scroll-mt-16 border-y border-neutral-200 bg-neutral-50 py-20 dark:border-neutral-800 dark:bg-neutral-900/40">
        <div :class="container">
          <div class="max-w-3xl">
            <p :class="eyebrow">{{ t('landing.roadmap.eyebrow') }}</p>
            <h2 :class="heading">{{ t('landing.roadmap.title') }}</h2>
            <p :class="lead">{{ t('landing.roadmap.body') }}</p>
          </div>
          <div class="mt-12 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div class="rounded-xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
              <h3 class="flex items-center gap-2 text-lg font-semibold text-neutral-900 dark:text-neutral-100">
                <CheckCircleIcon class="h-6 w-6 text-green-600 dark:text-green-500" />{{ t('landing.roadmap.today.title') }}
              </h3>
              <ul class="mt-5 space-y-3">
                <li v-for="item in todayItems" :key="rt(item)" class="flex gap-2.5 text-neutral-700 dark:text-neutral-300">
                  <CheckIcon class="mt-1 h-4 w-4 shrink-0 text-green-600 dark:text-green-500" />{{ rt(item) }}
                </li>
              </ul>
            </div>
            <div class="rounded-xl border border-dashed border-neutral-300 bg-white p-6 dark:border-neutral-700 dark:bg-neutral-900">
              <h3 class="flex items-center gap-2 text-lg font-semibold text-neutral-900 dark:text-neutral-100">
                <ClockIcon class="h-6 w-6 text-neutral-500" />{{ t('landing.roadmap.next.title') }}
              </h3>
              <ul class="mt-5 space-y-3">
                <li v-for="item in nextItems" :key="rt(item)" class="flex gap-2.5 text-neutral-700 dark:text-neutral-300">
                  <span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-neutral-400" />{{ rt(item) }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- ============================================================== FAQ -->
      <section id="faq" class="scroll-mt-16 py-20">
        <div :class="[container, 'max-w-3xl']">
          <h2 :class="[heading, 'mt-0']">{{ t('landing.faq.title') }}</h2>
          <div class="mt-8 divide-y divide-neutral-200 border-y border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
            <details v-for="item in faqItems" :key="rt(item.q)" class="group py-4">
              <summary class="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-neutral-900 dark:text-neutral-100">
                {{ rt(item.q) }}
                <span class="text-xl leading-none text-neutral-400 transition-transform group-open:rotate-45" aria-hidden="true">+</span>
              </summary>
              <p class="mt-3 leading-relaxed text-neutral-600 dark:text-neutral-400">{{ rt(item.a) }}</p>
            </details>
          </div>
        </div>
      </section>

      <!-- ============================================================== CTA -->
      <section class="border-t border-neutral-200 bg-blue-600 py-16 dark:border-neutral-800">
        <div :class="[container, 'flex flex-col items-center gap-5 text-center']">
          <h2 class="text-3xl font-semibold tracking-tight text-white">{{ t('landing.cta.title') }}</h2>
          <p class="text-lg text-blue-100">{{ t('landing.cta.body') }}</p>
          <RouterLink :to="{ name: 'login' }" class="inline-flex items-center justify-center rounded-lg bg-white px-6 py-3 text-sm font-semibold text-blue-700 shadow-sm hover:bg-blue-50">
            {{ t('landing.cta.primary') }}
          </RouterLink>
        </div>
      </section>
    </main>

    <footer class="py-10">
      <div :class="[container, 'flex flex-col items-center justify-between gap-4 text-sm text-neutral-500 sm:flex-row']">
        <div class="flex flex-col items-center gap-2 sm:flex-row sm:gap-4">
          <AppLogo />
          <span>{{ t('landing.footer.tagline') }}</span>
        </div>
        <span>© {{ year }} ERPIntel. {{ t('landing.footer.rights') }}</span>
      </div>
    </footer>
  </div>
</template>
