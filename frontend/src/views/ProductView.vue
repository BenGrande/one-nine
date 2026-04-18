<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { useHead } from '@unhead/vue'
import { RouterLink } from 'vue-router'
import DOMPurify from 'dompurify'
import PreorderForm from '../components/PreorderForm.vue'
import products from '../generated/products.json'
import type { ProductDetail, ProductSummary } from '../types/product'

const props = defineProps<{ slug: string }>()

const GlassView3D = defineAsyncComponent(() => import('../components/GlassView3D.vue'))

const list = products as unknown as ProductSummary[]
const summary = computed(() => list.find(p => p.slug === props.slug) || null)

const detail = ref<ProductDetail | null>(null)
const glass3dData = ref<unknown | null>(null)
const glassLoading = ref(false)
const notFound = ref(false)

async function loadDetail() {
  try {
    const mod = await import(`../generated/products/${props.slug}.json`)
    detail.value = (mod.default ?? mod) as ProductDetail
  } catch {
    notFound.value = list.findIndex(p => p.slug === props.slug) === -1
  }
}

async function loadGlass3D() {
  if (!detail.value?.glass3d_url || glass3dData.value) return
  glassLoading.value = true
  try {
    const res = await fetch(detail.value.glass3d_url)
    if (res.ok) glass3dData.value = await res.json()
  } finally {
    glassLoading.value = false
  }
}

onMounted(async () => {
  await loadDetail()
  await loadGlass3D()
})

const sanitizedHtml = computed(() =>
  detail.value?.content?.description_html
    ? DOMPurify.sanitize(detail.value.content.description_html, {
        ALLOWED_TAGS: ['p', 'strong', 'em', 'ul', 'li', 'h3'],
        ALLOWED_ATTR: [],
      })
    : '',
)

const related = computed(() => {
  if (!summary.value) return []
  return list
    .filter(p => p.slug !== summary.value!.slug && p.state === summary.value!.state)
    .slice(0, 3)
})

const productLd = computed(() => {
  const s = summary.value
  if (!s) return null
  const url = `https://www.splitthetee.com/products/${s.slug}`
  const image = s.hero_image ? `https://www.splitthetee.com${s.hero_image}` : undefined
  return {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: `${s.name} Pint Glass Set`,
    description: detail.value?.content?.headline
      || `A pint glass set etched with the holes of ${s.name}.`,
    image,
    brand: { '@type': 'Brand', name: 'Split the Tee' },
    sku: `stt-${s.slug}`,
    category: 'Drinkware / Pint Glasses',
    offers: {
      '@type': 'Offer',
      url,
      priceCurrency: 'USD',
      price: '49.00',
      availability: 'https://schema.org/PreOrder',
      priceValidUntil: new Date(Date.now() + 90 * 86400000).toISOString().slice(0, 10),
    },
  }
})

const breadcrumbLd = computed(() => {
  if (!summary.value) return null
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://www.splitthetee.com/' },
      { '@type': 'ListItem', position: 2, name: 'Courses', item: 'https://www.splitthetee.com/products' },
      {
        '@type': 'ListItem',
        position: 3,
        name: summary.value.name,
        item: `https://www.splitthetee.com/products/${summary.value.slug}`,
      },
    ],
  }
})

const combinedLdHtml = computed(() => {
  const scripts: unknown[] = []
  if (productLd.value) scripts.push(productLd.value)
  if (breadcrumbLd.value) scripts.push(breadcrumbLd.value)
  if (!scripts.length) return ''
  return `<script type="application/ld+json">${JSON.stringify(scripts)}<\/script>`
})

useHead(() => {
  const s = summary.value
  const title = s
    ? `${s.name} Pint Glass — Split the Tee`
    : 'Split the Tee — Course Pint Glass'
  const desc = detail.value?.content?.headline
    || (s ? `A pint glass etched with the holes of ${s.name}. Preorder now.` : '')
  const canonical = s
    ? `https://www.splitthetee.com/products/${s.slug}`
    : 'https://www.splitthetee.com/products'
  const image = s?.hero_image
    ? `https://www.splitthetee.com${s.hero_image}`
    : 'https://www.splitthetee.com/hero.jpg'

  return {
    title,
    meta: [
      { name: 'description', content: desc },
      { property: 'og:title', content: title },
      { property: 'og:description', content: desc },
      { property: 'og:type', content: 'product' },
      { property: 'og:image', content: image },
      { property: 'og:url', content: canonical },
      { name: 'twitter:card', content: 'summary_large_image' },
      { name: 'twitter:title', content: title },
      { name: 'twitter:image', content: image },
    ],
    link: [{ rel: 'canonical', href: canonical }],
  }
})

const prefillCourse = computed(() => {
  if (!summary.value || !detail.value) return undefined
  return {
    course_id: detail.value.course_id || null,
    course_name: summary.value.name,
    course_location: [summary.value.city, summary.value.state].filter(Boolean).join(', ') || null,
  }
})
</script>

<template>
  <div class="min-h-screen bg-white text-emerald-950">
    <div v-if="combinedLdHtml" v-html="combinedLdHtml" class="hidden" />
    <header class="border-b border-emerald-100">
      <div class="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
        <RouterLink to="/" class="flex items-center gap-3">
          <img src="/splitthetee.svg" alt="Split the Tee" class="h-8 w-auto" />
        </RouterLink>
        <nav class="text-sm text-emerald-700 flex gap-5">
          <RouterLink to="/products">All courses</RouterLink>
        </nav>
      </div>
    </header>

    <div v-if="notFound" class="max-w-6xl mx-auto px-6 py-20 text-center">
      <h1 class="text-2xl font-bold mb-3">Course not found</h1>
      <p class="text-emerald-700 mb-6">
        We don't have this course yet — but you can preorder any course from the home page
        and we'll etch it next.
      </p>
      <RouterLink
        to="/"
        class="inline-block px-5 py-3 rounded-xl bg-emerald-600 text-white font-semibold hover:bg-emerald-500"
      >
        Preorder any course
      </RouterLink>
    </div>

    <main v-else-if="summary" class="max-w-6xl mx-auto px-6 py-8 grid md:grid-cols-2 gap-10">
      <div>
        <div class="aspect-square bg-white border border-emerald-100 rounded-2xl overflow-hidden mb-4 flex items-center justify-center p-6">
          <img
            v-if="summary.hero_image"
            :src="summary.hero_image"
            :alt="`${summary.name} pint glass`"
            class="max-w-full max-h-full object-contain"
          />
          <div v-else class="text-emerald-300 text-sm">Preview generating</div>
        </div>
        <div
          v-if="glass3dData"
          class="rounded-2xl border border-emerald-100 overflow-hidden mb-4 bg-white h-80"
        >
          <GlassView3D
            :glass-data="glass3dData as any"
            :scores="{}"
            :holes="[]"
            :glass-number="1"
            :loading="glassLoading"
            :background-color="0xffffff"
            lock-vertical-rotation
          />
        </div>
        <img
          v-if="detail?.patio_image"
          :src="detail.patio_image"
          alt="The glass set on a clubhouse patio"
          class="w-full rounded-2xl"
        />
      </div>

      <section class="flex flex-col">
        <nav class="text-xs text-emerald-600 mb-2">
          <RouterLink to="/products" class="hover:underline">Courses</RouterLink>
          <span class="mx-1">/</span>
          <span>{{ summary.state || summary.country || '—' }}</span>
        </nav>
        <h1 class="text-3xl sm:text-4xl font-bold mb-1">{{ summary.name }}</h1>
        <p class="text-emerald-700 text-sm mb-5">
          {{ [summary.club_name, summary.city, summary.state].filter(Boolean).join(' · ') }}
        </p>

        <p v-if="detail?.content?.headline" class="text-lg text-emerald-900 font-medium mb-4">
          {{ detail.content.headline }}
        </p>

        <div
          v-if="sanitizedHtml"
          v-html="sanitizedHtml"
          class="prose prose-emerald max-w-none mb-5 text-emerald-900 text-sm leading-relaxed space-y-3"
        />

        <ul v-if="detail?.content?.bullets?.length" class="grid grid-cols-2 gap-2 mb-6">
          <li
            v-for="b in detail.content.bullets"
            :key="b"
            class="text-xs bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2"
          >
            {{ b }}
          </li>
        </ul>

        <div v-if="detail?.stats" class="grid grid-cols-3 gap-3 mb-6">
          <div class="text-center bg-emerald-50 rounded-xl p-3">
            <div class="text-xs text-emerald-600 uppercase tracking-wider">Par</div>
            <div class="text-xl font-bold">{{ detail.stats.total_par }}</div>
          </div>
          <div class="text-center bg-emerald-50 rounded-xl p-3">
            <div class="text-xs text-emerald-600 uppercase tracking-wider">Yards</div>
            <div class="text-xl font-bold">{{ detail.stats.total_yardage.toLocaleString() }}</div>
          </div>
          <div class="text-center bg-emerald-50 rounded-xl p-3">
            <div class="text-xs text-emerald-600 uppercase tracking-wider">Signature</div>
            <div class="text-xl font-bold">#{{ detail.stats.signature_hole ?? '—' }}</div>
          </div>
        </div>

        <div class="mt-auto bg-emerald-900 text-white rounded-2xl p-5">
          <h2 class="text-lg font-bold mb-1">Preorder the {{ summary.name }} set</h2>
          <p class="text-emerald-200 text-xs mb-4">
            $49 · ships in the first run. We'll email you when it's ready.
          </p>
          <PreorderForm :prefill-course="prefillCourse" />
        </div>
      </section>
    </main>

    <section v-if="summary && related.length" class="max-w-6xl mx-auto px-6 pb-16">
      <h2 class="text-xl font-semibold mb-4">More courses in {{ summary.state }}</h2>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <RouterLink
          v-for="r in related"
          :key="r.slug"
          :to="`/products/${r.slug}`"
          class="block bg-white border border-emerald-100 rounded-xl overflow-hidden hover:shadow-lg transition-shadow"
        >
          <div class="aspect-square bg-emerald-50">
            <img
              v-if="r.hero_image"
              :src="r.hero_image"
              :alt="`${r.name} pint glass`"
              loading="lazy"
              class="w-full h-full object-contain"
            />
          </div>
          <div class="p-3">
            <div class="font-medium text-sm truncate">{{ r.name }}</div>
            <div class="text-emerald-600 text-xs">{{ r.city }}, {{ r.state }}</div>
          </div>
        </RouterLink>
      </div>
    </section>
  </div>
</template>
