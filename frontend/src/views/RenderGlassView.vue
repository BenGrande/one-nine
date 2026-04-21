<script setup lang="ts">
/**
 * Build-time-only route used by scripts/generate_products.py via Playwright.
 * Renders a single GlassView3D on a chosen background (white or transparent)
 * and signals readiness via window.__renderReady so the capturing script knows
 * when to screenshot.
 */
import { defineAsyncComponent, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const GlassView3D = defineAsyncComponent(() => import('../components/GlassView3D.vue'))

const route = useRoute()
const glass3dData = ref<unknown | null>(null)
const loading = ref(true)

const angle = (route.query.angle as string) || 'front'
const bg = (route.query.bg as string) || 'white'

async function load() {
  const slug = route.params.slug as string
  const res = await fetch(`/products/${slug}/glass-3d.json`)
  if (res.ok) {
    glass3dData.value = await res.json()
  }
  loading.value = false
}

watch(glass3dData, (val) => {
  if (val) {
    ;(window as unknown as { __renderReady?: boolean }).__renderReady = true
  }
})

onMounted(() => {
  document.body.dataset.render = '1'
  document.body.dataset.angle = angle
  document.body.dataset.bg = bg
  load()
})
</script>

<template>
  <div
    :class="[
      'fixed inset-0 flex items-center justify-center',
      bg === 'white' ? 'bg-white' : 'bg-transparent',
    ]"
  >
    <div class="render-glass-container w-[720px] h-[720px]">
      <GlassView3D
        v-if="glass3dData"
        :glass-data="glass3dData as any"
        :scores="{}"
        :holes="[]"
        :glass-number="1"
        :loading="loading"
        :background-color="bg === 'white' ? 0xffffff : bg === 'transparent' ? -1 : undefined"
      />
    </div>
  </div>
</template>

<style scoped>
/* Override GlassView3D's fixed 200px height and dark background for render captures */
.render-glass-container :deep(.glass-3d-wrapper) {
  height: 100% !important;
  background: transparent !important;
}
</style>
