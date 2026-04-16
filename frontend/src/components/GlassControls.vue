<script setup lang="ts">
import { useDesignerStore, FONT_OPTIONS } from '../stores/designer'

const store = useDesignerStore()

const glassCountOptions = [1, 2, 3, 6]
const previewModes = [
  { label: 'Vinyl', value: 'vinyl-preview' as const },
  { label: 'Glass', value: 'glass' as const },
  { label: 'Rect', value: 'rect' as const },
  { label: 'Scoring', value: 'scoring-preview' as const },
  { label: 'C-White', value: 'cricut-white' as const },
  { label: 'C-Green', value: 'cricut-green' as const },
  { label: 'C-Tan', value: 'cricut-tan' as const },
]

function handleLogoUpload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (ev) => {
    store.setLogo(ev.target?.result as string)
  }
  reader.readAsDataURL(file)
}

function clearLogo() {
  store.setLogo(null)
}
</script>

<template>
  <div class="space-y-4">
    <!-- Recipient Name -->
    <div>
      <h3 class="text-[10px] uppercase tracking-wider text-gray-500 mb-2">Name</h3>
      <input v-model="store.recipientName" type="text" placeholder="Who is this for?"
        class="w-full px-2 py-1.5 text-xs rounded border bg-gray-800 border-gray-700 text-gray-300 placeholder-gray-600 focus:border-emerald-600 focus:outline-none" />
    </div>

    <!-- Glass Count -->
    <div>
      <h3 class="text-[10px] uppercase tracking-wider text-gray-500 mb-2">Glass</h3>
      <label class="block text-xs text-gray-400 mb-1">Glasses</label>
      <div class="flex gap-1">
        <button
          v-for="n in glassCountOptions"
          :key="n"
          @click="store.glassCount = n"
          class="flex-1 px-2 py-1.5 text-xs rounded border transition-colors"
          :class="store.glassCount === n
            ? 'bg-emerald-800 border-emerald-600 text-emerald-200'
            : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600'"
        >
          {{ n }}
        </button>
      </div>

      <label class="flex items-center gap-2 text-xs text-gray-400 mt-2 cursor-pointer">
        <input type="checkbox" v-model="store.twoColumnLayout" class="accent-emerald-500 w-3.5 h-3.5" />
        Two-column layout
      </label>

      <label class="flex items-center gap-2 text-xs text-gray-400 mt-1 cursor-pointer">
        <input type="checkbox" v-model="store.courseNameBanner" class="accent-emerald-500 w-3.5 h-3.5" />
        Course name banner
      </label>
    </div>

    <!-- Glass Dimensions -->
    <div>
      <h3 class="text-[10px] uppercase tracking-wider text-gray-500 mb-2">Dimensions</h3>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="block text-xs text-gray-500 mb-0.5">Height (mm)</label>
          <input v-model.number="store.glassDimensions.height" type="number" min="50" max="300" step="0.1"
            class="w-full px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-200 focus:outline-none focus:border-emerald-600" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-0.5">Top ⌀ (mm)</label>
          <input v-model.number="store.glassDimensions.topDiameter" type="number" min="20" max="200" step="0.1"
            class="w-full px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-200 focus:outline-none focus:border-emerald-600" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-0.5">Bottom ⌀ (mm)</label>
          <input v-model.number="store.glassDimensions.bottomDiameter" type="number" min="20" max="200" step="0.1"
            class="w-full px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-200 focus:outline-none focus:border-emerald-600" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-0.5">Wall (mm)</label>
          <input v-model.number="store.glassDimensions.wallThickness" type="number" min="0" max="10" step="0.5"
            class="w-full px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-200 focus:outline-none focus:border-emerald-600" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-0.5">Base (mm)</label>
          <input v-model.number="store.glassDimensions.baseThickness" type="number" min="0" max="15" step="0.5"
            class="w-full px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-200 focus:outline-none focus:border-emerald-600" />
        </div>
      </div>
    </div>

    <!-- Fill Mode -->
    <div>
      <label class="block text-xs text-gray-500 mb-0.5">Fill Mode</label>
      <select v-model="store.fillMode"
        class="w-full px-2 py-1.5 text-xs bg-gray-800 border border-gray-700 rounded text-gray-200 focus:outline-none focus:border-emerald-600">
        <option value="full">Full glass</option>
        <option value="can">Standard can (355ml)</option>
        <option value="custom">Custom padding</option>
      </select>
      <div v-if="store.fillMode === 'custom'" class="grid grid-cols-2 gap-2 mt-2">
        <div>
          <label class="block text-xs text-gray-500 mb-0.5">Top pad %</label>
          <input v-model.number="store.customTopPadding" type="number" min="0" max="50"
            class="w-full px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-200 focus:outline-none focus:border-emerald-600" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-0.5">Bot pad %</label>
          <input v-model.number="store.customBottomPadding" type="number" min="0" max="50"
            class="w-full px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-200 focus:outline-none focus:border-emerald-600" />
        </div>
      </div>
    </div>

    <!-- View Controls -->
    <div>
      <h3 class="text-[10px] uppercase tracking-wider text-gray-500 mb-2">View</h3>
      <label class="block text-xs text-gray-500 mb-0.5">Current Glass</label>
      <select v-model.number="store.currentGlass"
        class="w-full px-2 py-1.5 text-xs bg-gray-800 border border-gray-700 rounded text-gray-200 focus:outline-none focus:border-emerald-600 mb-2">
        <option v-for="i in store.glassCount" :key="i - 1" :value="i - 1">Glass {{ i }}</option>
      </select>

      <label class="block text-xs text-gray-500 mb-1">Preview Mode</label>
      <div class="flex gap-1">
        <button
          v-for="mode in previewModes"
          :key="mode.value"
          @click="store.previewMode = mode.value"
          class="flex-1 px-2 py-1.5 text-xs rounded border transition-colors"
          :class="store.previewMode === mode.value
            ? 'bg-emerald-800 border-emerald-600 text-emerald-200'
            : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600'"
        >{{ mode.label }}</button>
      </div>
    </div>

    <!-- Text & Logo -->
    <div>
      <h3 class="text-[10px] uppercase tracking-wider text-gray-500 mb-2">Text & Logo</h3>
      <label class="block text-xs text-gray-500 mb-0.5">Font</label>
      <select v-model="store.fontFamily"
        class="w-full px-2 py-1.5 text-xs bg-gray-800 border border-gray-700 rounded text-gray-200 focus:outline-none focus:border-emerald-600 mb-2">
        <option v-for="f in FONT_OPTIONS" :key="f.value" :value="f.value">{{ f.label }}</option>
      </select>

      <label class="flex items-center gap-2 text-xs text-gray-400 mb-2 cursor-pointer">
        <input type="checkbox" v-model="store.showText" class="accent-emerald-500 w-3.5 h-3.5" />
        Show text labels
      </label>

      <label class="flex items-center gap-2 text-xs text-gray-400 mb-2 cursor-pointer">
        <input type="checkbox" v-model="store.perHoleColors" class="accent-emerald-500 w-3.5 h-3.5" />
        Color code holes
      </label>

      <label class="block text-xs text-gray-500 mb-0.5">Logo image</label>
      <input type="file" accept="image/*" @change="handleLogoUpload"
        class="w-full text-xs text-gray-400 file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-xs file:bg-gray-700 file:text-gray-300 hover:file:bg-gray-600" />
      <div v-if="store.logoDataUrl" class="mt-2 flex items-center gap-2">
        <img :src="store.logoDataUrl" class="max-w-[60px] max-h-[30px] border border-gray-700 rounded" />
        <button @click="clearLogo" class="text-xs text-gray-500 hover:text-gray-300">Clear</button>
      </div>
    </div>
  </div>
</template>
