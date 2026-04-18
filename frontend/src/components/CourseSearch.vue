<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'

interface Location {
  city?: string
  state?: string
  country?: string
}

interface ApiCourse {
  id: number
  course_name?: string
  club_name?: string
  name?: string
  location?: Location
}

interface Suggestion {
  course_id: number
  course_name: string
  course_location: string | null
}

const emit = defineEmits<{
  select: [Suggestion]
  freeText: [string]
}>()

const query = ref('')
const suggestions = ref<Suggestion[]>([])
const open = ref(false)
const highlight = ref(-1)
const loading = ref(false)

let debounceTimer: ReturnType<typeof setTimeout> | null = null
let activeRequest = 0

function formatLocation(loc?: Location): string | null {
  if (!loc) return null
  const parts = [loc.city, loc.state, loc.country].filter(Boolean)
  return parts.length ? parts.join(', ') : null
}

function normalize(courses: ApiCourse[]): Suggestion[] {
  return courses.slice(0, 8).map(c => ({
    course_id: c.id,
    course_name: c.course_name || c.club_name || c.name || 'Unnamed course',
    course_location: formatLocation(c.location),
  }))
}

async function runSearch(q: string) {
  const requestId = ++activeRequest
  loading.value = true
  try {
    const res = await fetch(`/api/v1/search?q=${encodeURIComponent(q)}`)
    if (!res.ok) {
      if (requestId === activeRequest) suggestions.value = []
      return
    }
    const data = await res.json()
    if (requestId !== activeRequest) return
    suggestions.value = normalize(data.courses || [])
    highlight.value = suggestions.value.length ? 0 : -1
  } catch {
    if (requestId === activeRequest) suggestions.value = []
  } finally {
    if (requestId === activeRequest) loading.value = false
  }
}

watch(query, (val) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  const trimmed = val.trim()
  if (!trimmed) {
    suggestions.value = []
    open.value = false
    return
  }
  open.value = true
  debounceTimer = setTimeout(() => runSearch(trimmed), 250)
})

onBeforeUnmount(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})

function pick(s: Suggestion) {
  query.value = s.course_name
  open.value = false
  emit('select', s)
}

function submit() {
  if (highlight.value >= 0 && suggestions.value[highlight.value]) {
    pick(suggestions.value[highlight.value])
    return
  }
  const text = query.value.trim()
  if (!text) return
  open.value = false
  emit('freeText', text)
}

function onFocus() {
  if (query.value.trim()) open.value = true
}

function onBlur() {
  setTimeout(() => { open.value = false }, 150)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (!suggestions.value.length) return
    highlight.value = (highlight.value + 1) % suggestions.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (!suggestions.value.length) return
    highlight.value = highlight.value <= 0 ? suggestions.value.length - 1 : highlight.value - 1
  } else if (e.key === 'Enter') {
    e.preventDefault()
    submit()
  } else if (e.key === 'Escape') {
    open.value = false
  }
}
</script>

<template>
  <div class="relative">
    <input
      v-model="query"
      type="text"
      placeholder="Search for a course (or type your own)"
      autocomplete="off"
      @focus="onFocus"
      @blur="onBlur"
      @keydown="onKeydown"
      class="w-full px-4 py-3 bg-emerald-900 border border-emerald-700 rounded-xl text-white text-base placeholder-emerald-600 focus:outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400"
    />
    <div
      v-if="open && (suggestions.length || loading)"
      class="absolute z-20 mt-1 w-full bg-emerald-900 border border-emerald-700 rounded-xl shadow-xl overflow-hidden max-h-72 overflow-y-auto"
    >
      <div v-if="loading && !suggestions.length" class="px-4 py-3 text-emerald-400 text-sm">
        Searching...
      </div>
      <button
        v-for="(s, i) in suggestions"
        :key="s.course_id"
        type="button"
        @mousedown.prevent="pick(s)"
        @mouseenter="highlight = i"
        :class="[
          'w-full text-left px-4 py-2.5 transition-colors',
          highlight === i ? 'bg-emerald-700/60' : 'hover:bg-emerald-800/60',
        ]"
      >
        <div class="text-white text-sm font-medium">{{ s.course_name }}</div>
        <div v-if="s.course_location" class="text-emerald-400 text-xs">{{ s.course_location }}</div>
      </button>
    </div>
    <button
      type="button"
      @click="submit"
      class="mt-3 w-full px-4 py-3 bg-emerald-600 hover:bg-emerald-500 rounded-xl text-base font-semibold transition-colors"
    >
      Save my course
    </button>
  </div>
</template>
