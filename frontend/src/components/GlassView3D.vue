<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import type { Glass3DData } from '../types/glass3d'

const props = defineProps<{
  glassData: Glass3DData | null
  scores: Record<number, number>
  holes: { number: number; par: number }[]
  glassNumber: number
  loading: boolean
  /** Hex color for the canvas background. */
  backgroundColor?: number
  /** Lock vertical rotation so the glass only spins horizontally. */
  lockVerticalRotation?: boolean
}>()

const container = ref<HTMLElement | null>(null)
const initializing = ref(false)
const arSupported = ref(false)
const arActive = ref(false)
const arError = ref('')
const expanded = ref(false)

function toggleExpand() {
  expanded.value = !expanded.value
}

let scene: Awaited<ReturnType<typeof import('../composables/useGlassScene').useGlassScene>> | null = null
let arScene: Awaited<ReturnType<typeof import('../composables/useARScene').useARScene>> | null = null

async function initScene() {
  if (!container.value || !props.glassData || scene) return
  initializing.value = true
  try {
    const { useGlassScene } = await import('../composables/useGlassScene')
    scene = useGlassScene(container.value, props.glassData, {
      backgroundColor: props.backgroundColor,
      lockVerticalRotation: props.lockVerticalRotation,
    })
    scene.updateBeerLevel(props.scores, props.holes, props.glassNumber)

    // Check AR support
    checkARSupport()
  } finally {
    initializing.value = false
  }
}

async function checkARSupport() {
  // Show AR button on any mobile device — model-viewer handles iOS + Android
  const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  arSupported.value = isMobile
}

async function startAR() {
  if (!container.value || !props.glassData) return
  arError.value = ''
  try {
    const { useARScene } = await import('../composables/useARScene')
    arScene = useARScene(container.value, props.glassData)
    arScene.updateBeerLevel(props.scores, props.holes, props.glassNumber)
    const ok = await arScene.start()
    if (ok) {
      arActive.value = true
    } else {
      arError.value = 'Could not start AR session'
      arScene = null
    }
  } catch (e) {
    arError.value = 'AR failed to start'
    arScene = null
  }
}

function stopAR() {
  arScene?.stop()
  arScene = null
  arActive.value = false
}

onMounted(() => {
  if (props.glassData) initScene()
})

watch(() => props.glassData, (newData) => {
  if (newData && !scene) initScene()
})

watch(() => props.scores, (newScores) => {
  if (scene) scene.updateBeerLevel(newScores, props.holes, props.glassNumber)
  if (arScene) arScene.updateBeerLevel(newScores, props.holes, props.glassNumber)
}, { deep: true })

onUnmounted(() => {
  scene?.dispose()
  scene = null
  arScene?.stop()
  arScene = null
})
</script>

<template>
  <div :class="['glass-3d-wrapper', expanded ? 'glass-3d-expanded' : '']">
    <!-- Loading -->
    <div
      v-if="loading || initializing"
      class="absolute inset-0 flex items-center justify-center bg-[#111] z-10"
    >
      <div class="text-emerald-500 text-xs flex items-center gap-2">
        <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" class="opacity-25" />
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="3" stroke-linecap="round" class="opacity-75" />
        </svg>
        Loading 3D view...
      </div>
    </div>

    <!-- 3D Canvas -->
    <div ref="container" class="glass-canvas" />

    <!-- Expand/Collapse Button (bottom-left corner) -->
    <button
      @click="toggleExpand"
      class="expand-button"
      :title="expanded ? 'Collapse' : 'Expand'"
    >
      <!-- Expand icon -->
      <svg v-if="!expanded" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="15 3 21 3 21 9"/>
        <polyline points="9 21 3 21 3 15"/>
        <line x1="21" y1="3" x2="14" y2="10"/>
        <line x1="3" y1="21" x2="10" y2="14"/>
      </svg>
      <!-- Collapse icon -->
      <svg v-else class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="4 14 10 14 10 20"/>
        <polyline points="20 10 14 10 14 4"/>
        <line x1="14" y1="10" x2="21" y2="3"/>
        <line x1="3" y1="21" x2="10" y2="14"/>
      </svg>
    </button>

    <!-- AR Button (bottom-right corner) -->
    <button
      v-if="arSupported && !arActive"
      @click="startAR"
      class="ar-button"
      title="View in AR"
    >
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M2 7l4.41-4.41A2 2 0 017.83 2h8.34a2 2 0 011.42.59L22 7"/>
        <path d="M4 7v10a2 2 0 002 2h12a2 2 0 002-2V7"/>
        <circle cx="12" cy="13" r="3"/>
      </svg>
      <span class="text-[10px] font-medium">AR</span>
    </button>

    <!-- AR Active overlay -->
    <button
      v-if="arActive"
      @click="stopAR"
      class="ar-exit-button"
    >
      Exit AR
    </button>

    <!-- AR Error -->
    <div v-if="arError" class="absolute bottom-2 left-2 text-[10px] text-red-400 bg-black/60 px-2 py-1 rounded">
      {{ arError }}
    </div>
  </div>
</template>

<style scoped>
.glass-3d-wrapper {
  position: relative;
  width: 100%;
  height: 200px;
  overflow: hidden;
  background: #111;
  touch-action: none;
}

.glass-canvas {
  width: 100%;
  height: 100%;
}

.glass-canvas :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
}

.glass-3d-expanded {
  position: fixed !important;
  top: 0;
  left: 0;
  width: 100vw !important;
  height: 100vh !important;
  height: 100dvh !important;
  z-index: 50;
  border-radius: 0;
  margin: 0;
}

.expand-button {
  position: absolute;
  bottom: 8px;
  left: 8px;
  display: flex;
  align-items: center;
  padding: 6px;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: white;
  backdrop-filter: blur(4px);
  transition: background 0.2s;
  z-index: 5;
}

.expand-button:active {
  background: rgba(0, 0, 0, 0.8);
  transform: scale(0.95);
}

.ar-button {
  position: absolute;
  bottom: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: rgba(5, 150, 105, 0.7);
  border: 1px solid rgba(16, 185, 129, 0.5);
  border-radius: 9999px;
  color: white;
  backdrop-filter: blur(4px);
  transition: background 0.2s;
  z-index: 5;
}

.ar-button:active {
  background: rgba(5, 150, 105, 0.9);
  transform: scale(0.95);
}

.ar-exit-button {
  position: fixed;
  top: env(safe-area-inset-top, 16px);
  right: 16px;
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 9999px;
  color: white;
  font-size: 12px;
  font-weight: 500;
  backdrop-filter: blur(4px);
  z-index: 10000;
}

.ar-exit-button:active {
  background: rgba(0, 0, 0, 0.9);
}
</style>
