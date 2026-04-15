<script setup lang="ts">
import { computed } from 'vue'
import { useDesignerStore } from '../stores/designer'

const designer = useDesignerStore()

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  reexport: []
}>()

const allLayers = [
  { key: 'white' as const, label: 'White Layer', desc: 'Outlines, labels, ruler, zones, scores', color: '#ffffff', bg: 'bg-gray-700' },
  { key: 'blue' as const, label: 'Blue Layer', desc: 'Water hazards', color: '#5b9bd5', bg: 'bg-blue-900/40' },
  { key: 'green' as const, label: 'Green Layer', desc: 'Greens, tees, fairway accents', color: '#5cc654', bg: 'bg-emerald-900/50' },
  { key: 'tan' as const, label: 'Tan Layer', desc: 'Bunkers', color: '#e8dca0', bg: 'bg-amber-900/30' },
  { key: 'guide' as const, label: 'Placement Guide', desc: 'Full layout with markers', color: '#88aacc', bg: 'bg-blue-900/30' },
]

const layers = computed(() => {
  if (designer.consolidateLayers) {
    return allLayers.filter(l => l.key !== 'blue' && l.key !== 'tan').map(l =>
      l.key === 'white'
        ? { ...l, desc: 'Outlines, labels, ruler, zones, scores + water & bunkers' }
        : l
    )
  }
  return allLayers
})

function previewLayer(key: string) {
  if (key === 'white') designer.previewMode = 'cricut-white'
  else if (key === 'blue') designer.previewMode = 'cricut-blue'
  else if (key === 'green') designer.previewMode = 'cricut-green'
  else if (key === 'tan') designer.previewMode = 'cricut-tan'
}
</script>

<template>
  <div v-if="visible" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" @click.self="emit('close')">
    <div class="bg-gray-900 border border-gray-700 rounded-lg w-[520px] max-h-[80vh] flex flex-col shadow-xl">
      <!-- Header -->
      <div class="px-5 py-3 border-b border-gray-700 flex items-center justify-between">
        <div>
          <h2 class="text-sm font-semibold text-gray-200">Export for Cricut</h2>
          <p class="text-[10px] text-gray-500 mt-0.5">Print at 100% scale — verify with 10mm reference bar</p>
        </div>
        <button @click="emit('close')" class="text-gray-500 hover:text-gray-300 text-lg">&times;</button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-5">
        <!-- Loading state -->
        <div v-if="designer.cricutLoading" class="flex items-center justify-center py-12 text-gray-400">
          <span class="inline-block w-5 h-5 border-2 border-gray-600 border-t-emerald-400 rounded-full animate-spin mr-3" />
          Generating Cricut layers...
        </div>

        <!-- Error state -->
        <div v-else-if="!designer.cricutSvgs && designer.statusMessage.includes('not available')" class="text-center py-12">
          <p class="text-red-400 text-sm">Cricut export failed</p>
          <p class="text-gray-500 text-xs mt-1">{{ designer.statusMessage }}</p>
        </div>

        <!-- Not available -->
        <div v-else-if="!designer.cricutSvgs" class="text-center py-12">
          <p class="text-gray-400 text-sm">Cricut export not yet generated</p>
          <p class="text-gray-600 text-xs mt-1">If the API is not available, this feature will show a placeholder</p>
        </div>

        <!-- Layer previews -->
        <div v-else class="space-y-3">
          <!-- Consolidate toggle -->
          <label class="flex items-center gap-2.5 px-4 py-2.5 rounded-lg border border-gray-700 bg-gray-800/50 cursor-pointer hover:border-gray-600 transition-colors">
            <input
              type="checkbox"
              v-model="designer.consolidateLayers"
              @change="emit('reexport')"
              class="accent-emerald-500 w-3.5 h-3.5"
            />
            <div>
              <div class="text-xs font-medium text-gray-200">Consolidate layers</div>
              <div class="text-[10px] text-gray-500">Merge blue &amp; tan into white (for 2-vinyl setups)</div>
            </div>
          </label>

          <div
            v-for="layer in layers"
            :key="layer.key"
            class="rounded-lg border border-gray-700 overflow-hidden"
            :class="layer.bg"
          >
            <div class="flex items-center gap-3 px-4 py-2.5">
              <span class="w-3 h-3 rounded-full border border-white/20 shrink-0" :style="{ background: layer.color }" />
              <div class="flex-1 min-w-0">
                <div class="text-xs font-medium text-gray-200">{{ layer.label }}</div>
                <div class="text-[10px] text-gray-500">{{ layer.desc }}</div>
              </div>
              <button
                v-if="layer.key !== 'guide'"
                @click="previewLayer(layer.key)"
                class="px-2 py-1 text-[10px] bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded text-gray-400 transition-colors"
              >Preview</button>
              <button
                @click="designer.downloadCricutLayer(layer.key)"
                :disabled="!designer.cricutSvgs?.[layer.key]"
                class="px-2 py-1 text-[10px] bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded text-gray-400 transition-colors disabled:opacity-40"
              >Download</button>
            </div>
            <!-- SVG thumbnail -->
            <div
              v-if="designer.cricutSvgs?.[layer.key]"
              class="px-4 pb-3"
            >
              <div
                v-html="designer.cricutSvgs[layer.key]"
                class="max-h-20 overflow-hidden rounded border border-gray-700/50 [&>svg]:w-full [&>svg]:h-auto [&>svg]:max-h-20"
              />
            </div>
          </div>

          <!-- Scale info -->
          <div class="rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3">
            <p class="text-[11px] text-gray-400">
              <strong class="text-gray-300">Scale verification:</strong>
              Print at 100% scale. Each SVG includes a 10mm reference bar on the right edge — measure it after printing to verify accuracy.
            </p>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-5 py-3 border-t border-gray-700 flex items-center gap-2">
        <button
          @click="designer.downloadAllCricutLayers()"
          :disabled="!designer.cricutSvgs"
          class="px-4 py-2 text-xs bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded font-medium transition-colors"
        >Download All (ZIP)</button>
        <button
          @click="emit('close')"
          class="px-4 py-2 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 rounded transition-colors"
        >Close</button>
      </div>
    </div>
  </div>
</template>
