<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCourseStore } from '../stores/course'
import { useDesignerStore } from '../stores/designer'
import GlassControls from '../components/GlassControls.vue'
import LayerControls from '../components/LayerControls.vue'
import SvgPreview from '../components/SvgPreview.vue'
import CricutExportPanel from '../components/CricutExportPanel.vue'

const route = useRoute()
const router = useRouter()
const courseStore = useCourseStore()
const designer = useDesignerStore()

const svgPreview = ref<InstanceType<typeof SvgPreview> | null>(null)
const courseSearchQuery = ref('')
const courseSearchResults = ref<any[]>([])
const showLoadModal = ref(false)
const showCricutPanel = ref(false)
const showHeaderResults = ref(false)
const savedSettingsList = ref<any[]>([])
let searchTimeout: ReturnType<typeof setTimeout> | null = null

// Debounced course search
function onCourseSearchInput() {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(async () => {
    const q = courseSearchQuery.value.trim()
    if (q.length < 2) {
      courseSearchResults.value = []
      return
    }
    try {
      const res = await fetch(`/api/v1/search?q=${encodeURIComponent(q)}`)
      const data = await res.json()
      courseSearchResults.value = data.courses || []
      showHeaderResults.value = true
    } catch {
      courseSearchResults.value = []
    }
  }, 400)
}

async function selectSearchCourse(course: any) {
  courseSearchResults.value = []
  showHeaderResults.value = false
  courseSearchQuery.value = course.course_name
  await courseStore.loadCourse(course)
  designer.applyFontHint(courseStore.courseData)
  triggerRender()

  // Persist course in URL so it survives page reload
  router.replace({
    query: {
      lat: course.location?.latitude,
      lng: course.location?.longitude,
      courseId: course.id,
    },
  })
}

// Debounced render
let renderTimeout: ReturnType<typeof setTimeout> | null = null
function triggerRender() {
  if (renderTimeout) clearTimeout(renderTimeout)
  renderTimeout = setTimeout(() => {
    designer.renderPreview(courseStore.courseData)
  }, 300)
}

// Watch designer state changes to trigger re-render
watch(
  () => [
    designer.glassCount,
    designer.currentGlass,
    designer.glassDimensions.height,
    designer.glassDimensions.topRadius,
    designer.glassDimensions.bottomRadius,
    designer.glassDimensions.wallThickness,
    designer.glassDimensions.baseThickness,
    designer.fillMode,
    designer.customTopPadding,
    designer.customBottomPadding,
    designer.previewMode,
    designer.hiddenLayers,
    designer.styles,
    designer.fontFamily,
    designer.showText,
    designer.perHoleColors,
    designer.logoDataUrl,
    designer.twoColumnLayout,
    designer.courseNameBanner,
  ],
  () => {
    if (courseStore.courseData) triggerRender()
  },
  { deep: true }
)

// Load course from route params on mount
onMounted(async () => {
  const lat = route.query.lat as string
  const lng = route.query.lng as string
  const courseId = route.query.courseId as string
  // Restore glass set ID from URL
  const savedGlassSetId = route.query.glassSetId as string
  if (savedGlassSetId) {
    designer.glassSetId = savedGlassSetId
  }
  if (courseId) {
    try {
      let url = `/api/v1/course-holes?courseId=${courseId}`
      if (lat) url += `&lat=${lat}`
      if (lng) url += `&lng=${lng}`
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        // Normalize snake_case API response (same as course.ts loadCourse)
        data.courseName = data.course_name || data.courseName || ''
        data.fontHint = data.font_hint || null
        courseStore.courseData = data
        courseSearchQuery.value = data.courseName || ''
        designer.applyFontHint(data)
        triggerRender()
      }
    } catch {
      designer.statusMessage = 'Failed to load course data'
    }
  }
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('click', onClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('click', onClickOutside)
})

function onClickOutside(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.header-search')) {
    showHeaderResults.value = false
  }
}

// Keyboard shortcuts
function onKeyDown(e: KeyboardEvent) {
  // Ignore if typing in an input/select/textarea
  const tag = (e.target as HTMLElement).tagName
  if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return

  switch (e.key) {
    case '1': designer.glassCount = 1; break
    case '2': designer.glassCount = 2; break
    case '3': designer.glassCount = 3; break
    case '6': designer.glassCount = 6; break
    case 'v': designer.previewMode = 'vinyl-preview'; break
    case 'g': designer.previewMode = 'glass'; break
    case 'r': designer.previewMode = 'rect'; break
    case 's': designer.previewMode = 'scoring-preview'; break
  }
}

function handleResetZoom() {
  svgPreview.value?.resetZoom()
}

async function handleSave() {
  const course = courseStore.selectedCourse
  await designer.saveSettings(
    courseStore.courseData?.courseName || course?.course_name || 'Untitled',
    course?.id || null,
    course?.location?.latitude || null,
    course?.location?.longitude || null
  )
}

async function handleOpenLoadModal() {
  savedSettingsList.value = await designer.loadSettingsList()
  showLoadModal.value = true
}

async function handleLoadSetting(id: string) {
  const s = await designer.loadSettings(id)
  showLoadModal.value = false
  if (s?.courseId) {
    try {
      let url = `/api/v1/course-holes?courseId=${s.courseId}`
      if (s.lat) url += `&lat=${s.lat}`
      if (s.lng) url += `&lng=${s.lng}`
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        data.courseName = data.course_name || data.courseName || s.courseName || ''
        data.fontHint = data.font_hint || null
        courseStore.courseData = data
        courseSearchQuery.value = data.courseName || ''
        triggerRender()
      }
    } catch {
      designer.statusMessage = 'Failed to load course data for setting'
    }
  }
}

function handleExport() {
  designer.exportSvg()
}

async function handleExportAll() {
  await designer.exportAllSvg(courseStore.courseData)
}

async function handleCricutExport() {
  await designer.exportCricut(courseStore.courseData)
  showCricutPanel.value = true
}

// Glass template info for tooltip
function glassInfo(): string {
  const d = designer.glassDimensions
  return `H: ${d.height}mm | Top: \u2300${(d.topRadius * 2).toFixed(0)}mm | Bot: \u2300${(d.bottomRadius * 2).toFixed(0)}mm`
}
</script>

<template>
  <div class="flex flex-col h-screen bg-gray-950 text-gray-200">
    <!-- Header -->
    <header class="bg-gray-900 px-6 py-3 flex items-center gap-4 border-b border-gray-800 shrink-0">
      <img src="/splitthetee.svg" alt="Split the Tee" class="w-7 h-7 rounded" />
      <h1 class="text-lg font-semibold text-emerald-400">Glass Designer</h1>

      <!-- Course Search -->
      <div class="header-search relative ml-auto flex items-center gap-3">
        <input
          v-model="courseSearchQuery"
          @input="onCourseSearchInput"
          @focus="showHeaderResults = true"
          type="text"
          placeholder="Search courses..."
          class="w-64 px-3 py-1.5 text-xs bg-gray-800 border border-gray-700 rounded text-gray-200 focus:outline-none focus:border-emerald-600"
        />
        <div v-if="showHeaderResults && courseSearchResults.length" class="absolute top-full left-0 mt-1 w-64 max-h-48 overflow-y-auto border border-gray-700 rounded bg-gray-800 shadow-xl z-50">
          <div
            v-for="(c, i) in courseSearchResults"
            :key="i"
            @click="selectSearchCourse(c)"
            class="px-3 py-2 text-xs cursor-pointer hover:bg-gray-700 border-b border-gray-700 last:border-0"
          >
            {{ c.course_name }}
            <span class="text-gray-500">— {{ c.location?.city || '' }}</span>
          </div>
        </div>
        <span v-if="designer.courseName" class="text-sm text-white font-medium whitespace-nowrap">{{ designer.courseName }}</span>
      </div>
      <span class="text-[10px] text-gray-600 ml-2 shrink-0" :title="glassInfo()">{{ glassInfo() }}</span>
    </header>

    <!-- Three-column layout -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Left Sidebar: Controls -->
      <aside class="w-[300px] min-w-[300px] bg-gray-900 border-r border-gray-800 overflow-y-auto p-3 space-y-4 shrink-0">
        <!-- Glass & View Controls -->
        <GlassControls />

        <!-- Actions -->
        <div>
          <h3 class="text-[10px] uppercase tracking-wider text-gray-500 mb-2">Actions</h3>
          <div class="flex flex-wrap gap-1.5">
            <button @click="handleExport" :disabled="!designer.svgContent" class="px-3 py-1.5 text-xs bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded font-medium transition-colors">
              Export SVG
            </button>
            <button @click="handleExportAll" :disabled="!courseStore.courseData?.holes?.length" class="px-3 py-1.5 text-xs bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded font-medium transition-colors">
              Export All
            </button>
            <button @click="handleCricutExport" :disabled="!courseStore.courseData?.holes?.length" class="px-3 py-1.5 text-xs bg-amber-700 hover:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded font-medium transition-colors">
              Export Cricut
            </button>
            <button @click="designer.openPrintTest()" :disabled="!designer.svgContent" class="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed text-gray-200 rounded transition-colors">
              Print Test
            </button>
            <button @click="handleSave" class="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 rounded transition-colors">
              Save Settings
            </button>
            <button @click="handleOpenLoadModal" class="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 rounded transition-colors">
              Load Settings
            </button>
          </div>
        </div>
      </aside>

      <!-- Center: SVG Preview -->
      <div class="flex-1 flex flex-col overflow-hidden">
        <!-- Toolbar -->
        <div class="flex items-center gap-2 px-4 py-2 bg-gray-900/80 border-b border-gray-800 shrink-0">
          <select
            v-model.number="designer.currentGlass"
            class="px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-300 focus:outline-none"
          >
            <option v-for="i in designer.glassCount" :key="i - 1" :value="i - 1">Glass {{ i }}</option>
          </select>
          <div class="flex-1" />
          <button
            v-for="mode in [
              { value: 'vinyl-preview', label: 'Vinyl', key: 'V' },
              { value: 'glass', label: 'Glass', key: 'G' },
              { value: 'rect', label: 'Rect', key: 'R' },
              { value: 'scoring-preview', label: 'Scoring', key: 'S' },
              { value: 'cricut-white', label: 'C-Wht', key: '' },
              { value: 'cricut-blue', label: 'C-Blu', key: '' },
              { value: 'cricut-green', label: 'C-Grn', key: '' },
              { value: 'cricut-tan', label: 'C-Tan', key: '' },
            ]"
            :key="mode.value"
            @click="designer.previewMode = mode.value as any"
            class="px-3 py-1 text-xs rounded border transition-colors"
            :class="designer.previewMode === mode.value
              ? 'bg-emerald-900/50 border-emerald-600 text-emerald-400'
              : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600'"
            :title="`${mode.label} mode (${mode.key})`"
          >{{ mode.label }}</button>
          <button
            @click="designer.showScoreLines = !designer.showScoreLines; triggerRender()"
            class="px-3 py-1 text-xs rounded border transition-colors"
            :class="designer.showScoreLines
              ? 'bg-yellow-900/50 border-yellow-600 text-yellow-400'
              : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600'"
            title="Toggle score zone lines overlay"
          >{{ designer.showScoreLines ? 'Lines ON' : 'Lines' }}</button>
          <button @click="handleResetZoom" class="px-3 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-400 hover:border-gray-600 transition-colors">
            Reset Zoom
          </button>
        </div>

        <!-- SVG Display -->
        <SvgPreview
          ref="svgPreview"
          :svg-content="designer.svgContent"
          :loading="designer.loading"
        />
      </div>

      <!-- Right Sidebar: Layers & Styles -->
      <aside class="w-[200px] min-w-[200px] bg-gray-900 border-l border-gray-800 overflow-y-auto p-3 shrink-0">
        <LayerControls />
      </aside>
    </div>

    <!-- Status Bar -->
    <div class="px-4 py-1.5 bg-gray-900 border-t border-gray-800 text-[11px] text-gray-500 shrink-0 flex items-center gap-4">
      <span>{{ designer.statusMessage }}</span>
      <span class="ml-auto text-gray-600">Keys: 1-3/6 glass count | v/g/r/s mode</span>
    </div>

    <!-- Cricut Export Panel -->
    <CricutExportPanel :visible="showCricutPanel" @close="showCricutPanel = false" @reexport="designer.exportCricut(courseStore.courseData)" />

    <!-- Load Settings Modal -->
    <div v-if="showLoadModal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" @click.self="showLoadModal = false">
      <div class="bg-gray-900 border border-gray-700 rounded-lg w-96 max-h-[60vh] flex flex-col shadow-xl">
        <div class="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
          <h2 class="text-sm font-semibold text-gray-200">Load Settings</h2>
          <button @click="showLoadModal = false" class="text-gray-500 hover:text-gray-300 text-lg">&times;</button>
        </div>
        <div class="flex-1 overflow-y-auto p-3">
          <div v-if="savedSettingsList.length === 0" class="text-center text-gray-500 text-sm py-6">
            No saved settings found
          </div>
          <div
            v-for="s in savedSettingsList"
            :key="s.filename || s.id"
            @click="handleLoadSetting(s.filename || s.id)"
            class="px-3 py-2 rounded cursor-pointer hover:bg-gray-800 border-b border-gray-800 last:border-0"
          >
            <div class="text-sm text-gray-200">{{ s.courseName || s.course_name || 'Untitled' }}</div>
            <div class="text-[10px] text-gray-500">
              {{ s.savedAt ? new Date(s.savedAt).toLocaleDateString() : '' }}
              <span v-if="s.glassCount"> &middot; {{ s.glassCount }} glasses</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
