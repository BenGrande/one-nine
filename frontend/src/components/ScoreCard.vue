<script setup lang="ts">
import { ref, computed, defineAsyncComponent, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '../stores/game'

const GlassView3D = defineAsyncComponent(() => import('./GlassView3D.vue'))

const game = useGameStore()
const selectedHole = ref<number | null>(null)
const selectedPlayerIndex = ref<number | null>(null)
const scoreFlash = ref<{ hole: number; playerIndex: number } | null>(null)
const viewMode = ref<'map' | 'glass'>('map')
const confirmNewGame = ref(false)
const addingPlayer = ref(false)
const newPlayerName = ref('')
const addPlayerError = ref('')

async function submitNewPlayer() {
  const name = newPlayerName.value.trim()
  if (!name) {
    addPlayerError.value = 'Enter a name'
    return
  }
  addPlayerError.value = ''
  const ok = await game.addPlayer(name)
  if (!ok) {
    addPlayerError.value = 'Could not add player'
    return
  }
  game.switchPlayer(game.localPlayers.length - 1)
  newPlayerName.value = ''
  addingPlayer.value = false
}

function cancelAddPlayer() {
  addingPlayer.value = false
  newPlayerName.value = ''
  addPlayerError.value = ''
}

async function handleNewGame() {
  if (!confirmNewGame.value) {
    confirmNewGame.value = true
    setTimeout(() => { confirmNewGame.value = false }, 3000)
    return
  }
  await game.resetAndStartNew()
}

async function loadGlass3D() {
  if (!game.glass3dData && !game.glass3dLoading) {
    await game.fetchGlass3DData()
  }
}

// Map viewBox-based zoom (keeps SVG vector-crisp at any zoom)
const mapContainer = ref<HTMLElement | null>(null)
const mapScale = ref(1)
// panX/panY in viewBox coordinate units
const panX = ref(0)
const panY = ref(0)
let mapPanning = false
let mapPanStartX = 0
let mapPanStartY = 0
let mapPanOriginX = 0
let mapPanOriginY = 0
let lastPinchDist = 0
let origVB = { x: 0, y: 0, w: 600, h: 300 }

// Prepare the SVG for initial injection (strip fixed size so it fills container)
const initialMapSvg = computed(() => {
  if (!game.courseMapSvg) return ''
  // Parse and store original viewBox
  const match = game.courseMapSvg.match(/viewBox="([^"]+)"/)
  if (match) {
    const [x, y, w, h] = match[1].split(/\s+/).map(Number)
    origVB = { x, y, w, h }
  }
  return game.courseMapSvg
    .replace(/\bwidth="\d+(\.\d+)?"/, 'width="100%"')
    .replace(/\bheight="\d+(\.\d+)?"/, 'height="100%"')
})

// Directly mutate the SVG element's viewBox — no DOM replacement
function updateSvgViewBox() {
  const el = mapContainer.value
  if (!el) return
  const svg = el.querySelector('svg')
  if (!svg) return
  const w = origVB.w / mapScale.value
  const h = origVB.h / mapScale.value
  const cx = origVB.x + (origVB.w - w) / 2 - panX.value
  const cy = origVB.y + (origVB.h - h) / 2 - panY.value
  svg.setAttribute('viewBox', `${cx} ${cy} ${w} ${h}`)
}

function onMapTouchStart(e: TouchEvent) {
  if (e.touches.length === 2) {
    const dx = e.touches[0].clientX - e.touches[1].clientX
    const dy = e.touches[0].clientY - e.touches[1].clientY
    lastPinchDist = Math.hypot(dx, dy)
    mapPanning = false
  } else if (e.touches.length === 1 && mapScale.value > 1) {
    mapPanning = true
    mapPanStartX = e.touches[0].clientX
    mapPanStartY = e.touches[0].clientY
    mapPanOriginX = panX.value
    mapPanOriginY = panY.value
  }
}

function onMapTouchMove(e: TouchEvent) {
  if (e.touches.length === 2) {
    e.preventDefault()
    const dx = e.touches[0].clientX - e.touches[1].clientX
    const dy = e.touches[0].clientY - e.touches[1].clientY
    const dist = Math.hypot(dx, dy)
    if (lastPinchDist > 0) {
      const factor = dist / lastPinchDist
      mapScale.value = Math.max(1, Math.min(14, mapScale.value * factor))
      updateSvgViewBox()
    }
    lastPinchDist = dist
  } else if (e.touches.length === 1 && mapPanning && mapScale.value > 1) {
    e.preventDefault()
    const el = mapContainer.value
    if (!el) return
    const pxPerUnit = el.clientWidth / (origVB.w / mapScale.value)
    panX.value = mapPanOriginX + (e.touches[0].clientX - mapPanStartX) / pxPerUnit
    panY.value = mapPanOriginY + (e.touches[0].clientY - mapPanStartY) / pxPerUnit
    updateSvgViewBox()
  }
}

function onMapTouchEnd(e: TouchEvent) {
  if (e.touches.length < 2) {
    lastPinchDist = 0
  }
  if (e.touches.length === 0) {
    mapPanning = false
    if (mapScale.value < 1.1) {
      mapScale.value = 1
      panX.value = 0
      panY.value = 0
      updateSvgViewBox()
    }
  }
}

const scoreOptions = [-1, 0, 1, 2, 3, 4, 5]

// Split holes into front 9 / back 9 style groupings
const holeGroups = computed(() => {
  const all = Array.from({ length: game.totalHoles }, (_, i) => i + 1)
  if (all.length <= 9) return [all]
  const mid = Math.ceil(all.length / 2)
  return [all.slice(0, mid), all.slice(mid)]
})

function holeInfo(holeNum: number) {
  return game.holes.find(h => h.number === holeNum) || { number: holeNum, par: 4, yards: 0, handicap: 0 }
}

function relToPar(score: number | undefined, par: number): number | null {
  if (score === undefined) return null
  return score - par
}

function scoreClass(score: number | undefined, par: number): string {
  if (score === undefined) return ''
  const rel = score - par
  if (rel <= -2) return 'bg-amber-400 text-amber-950 font-bold'
  if (rel === -1) return 'bg-red-500 text-white font-bold'
  if (rel === 0) return 'bg-emerald-600 text-white'
  if (rel === 1) return 'bg-sky-400 text-sky-950'
  if (rel === 2) return 'bg-sky-600 text-white'
  return 'bg-sky-800 text-white'
}

function otherPlayerScore(playerId: string, holeNum: number): number | undefined {
  const player = game.otherPlayers.find(p => p.player_id === playerId)
  if (!player) return undefined
  const s = player.scores_by_hole?.find((s: any) => s.hole_number === holeNum)
  return s?.score
}

function groupTotal(group: number[], playerScores: Record<number, number>): number {
  let total = 0
  for (const h of group) {
    if (playerScores[h] !== undefined) total += playerScores[h]
  }
  return total
}

function groupPar(group: number[]): number {
  return group.reduce((sum, h) => sum + holeInfo(h).par, 0)
}

function otherPlayerGroupTotal(playerId: string, group: number[]): number {
  let total = 0
  for (const h of group) {
    const s = otherPlayerScore(playerId, h)
    if (s !== undefined) total += s
  }
  return total
}

function grandTotal(playerScores: Record<number, number>): number {
  return Object.values(playerScores).reduce((a, b) => a + b, 0)
}

function totalPar(): number {
  return Array.from({ length: game.totalHoles }, (_, i) => i + 1)
    .reduce((sum, h) => sum + holeInfo(h).par, 0)
}

function playerCumulative(playerScores: Record<number, number>): number {
  let total = 0
  for (const [hole, score] of Object.entries(playerScores)) {
    total += score - holeInfo(Number(hole)).par
  }
  return total
}

function formatRelPar(n: number): string {
  if (n === 0) return 'E'
  return n > 0 ? `+${n}` : `${n}`
}

function openScoreInput(holeNum: number, playerIndex: number) {
  selectedHole.value = holeNum
  selectedPlayerIndex.value = playerIndex
}

function vibrate() {
  try { navigator.vibrate?.(30) } catch { /* not available */ }
}

const selectedPlayer = computed(() => {
  if (selectedPlayerIndex.value === null) return null
  return game.localPlayers[selectedPlayerIndex.value] || null
})

function scoreForSelectedHole(): number | undefined {
  if (selectedHole.value === null || !selectedPlayer.value) return undefined
  return selectedPlayer.value.scores[selectedHole.value]
}

async function handleScore(rel: number) {
  if (selectedHole.value === null || selectedPlayerIndex.value === null) return
  const hole = selectedHole.value
  const pIdx = selectedPlayerIndex.value
  const par = holeInfo(hole).par
  const actual = par + rel
  const ok = await game.submitScore(hole, actual, pIdx)
  if (ok !== false) {
    vibrate()
    scoreFlash.value = { hole, playerIndex: pIdx }
    setTimeout(() => { scoreFlash.value = null }, 400)
    selectedHole.value = null
    selectedPlayerIndex.value = null
    if (pIdx === game.activePlayerIndex) game.advanceToNextUnscored()
  }
}

async function handlePenalty() {
  if (selectedHole.value === null || selectedPlayerIndex.value === null) return
  const hole = selectedHole.value
  const pIdx = selectedPlayerIndex.value
  const par = holeInfo(hole).par
  await game.submitScore(hole, par + 8, pIdx)
  vibrate()
  selectedHole.value = null
  selectedPlayerIndex.value = null
  if (pIdx === game.activePlayerIndex) game.advanceToNextUnscored()
}

async function handleRemoveScore() {
  if (selectedHole.value === null || selectedPlayerIndex.value === null) return
  const hole = selectedHole.value
  const pIdx = selectedPlayerIndex.value
  await game.removeScore(hole, pIdx)
  vibrate()
  selectedHole.value = null
  selectedPlayerIndex.value = null
}

function closeModal() {
  selectedHole.value = null
  selectedPlayerIndex.value = null
}

function preventZoom(e: Event) {
  e.preventDefault()
}

onMounted(() => {
  game.startScorePolling()
  // iOS Safari ignores user-scalable=no; block the gesture explicitly.
  document.addEventListener('gesturestart', preventZoom, { passive: false })
  document.addEventListener('gesturechange', preventZoom, { passive: false })
  document.addEventListener('gestureend', preventZoom, { passive: false })
})

onUnmounted(() => {
  game.stopScorePolling()
  document.removeEventListener('gesturestart', preventZoom)
  document.removeEventListener('gesturechange', preventZoom)
  document.removeEventListener('gestureend', preventZoom)
})
</script>

<template>
  <div class="scorecard-root">
    <!-- Header -->
    <header class="bg-emerald-900 px-4 py-3 flex items-center justify-between shrink-0 border-b border-emerald-800">
      <div class="min-w-0">
        <h1 class="text-lg font-bold tracking-tight truncate">{{ game.courseName || 'Split the Tee' }}</h1>
        <p class="text-emerald-400 text-xs">{{ game.playerName }} &middot; Glass {{ game.currentGlassNumber }}</p>
      </div>
      <div class="text-right shrink-0 pl-3">
        <div class="text-2xl font-bold tabular-nums" :class="game.cumulativeScore < 0 ? 'text-red-400' : game.cumulativeScore === 0 ? 'text-emerald-300' : 'text-white'">
          {{ formatRelPar(game.cumulativeScore) }}
        </div>
        <div class="text-[10px] text-emerald-500">{{ game.holesScored }}/{{ game.totalHoles }} holes</div>
      </div>
    </header>

    <!-- Player Switcher (with mid-game add) -->
    <div class="flex flex-wrap items-center justify-center gap-1.5 px-4 py-2 shrink-0">
      <button
        v-for="(p, i) in game.localPlayers"
        :key="p.playerId"
        @click="game.switchPlayer(i)"
        class="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
        :class="i === game.activePlayerIndex
          ? 'bg-emerald-600 text-white shadow-sm'
          : 'bg-emerald-900/60 text-emerald-500 border border-emerald-800/50 hover:bg-emerald-800/60'"
      >
        {{ p.playerName }}
      </button>

      <button
        v-if="!addingPlayer"
        @click="addingPlayer = true"
        aria-label="Add player"
        class="px-2.5 py-1.5 rounded-full text-xs font-medium bg-emerald-900/60 text-emerald-300 border border-emerald-800/50 hover:bg-emerald-800/60 transition-all"
      >
        + Add player
      </button>

      <div v-else class="flex items-center gap-1.5">
        <input
          v-model="newPlayerName"
          type="text"
          placeholder="Player name"
          autofocus
          @keydown.enter="submitNewPlayer"
          @keydown.esc="cancelAddPlayer"
          class="px-3 py-1.5 rounded-full text-xs bg-emerald-900 border border-emerald-700 text-white placeholder-emerald-600 focus:outline-none focus:border-emerald-400"
        />
        <button
          @click="submitNewPlayer"
          :disabled="game.loading"
          class="px-3 py-1.5 rounded-full text-xs font-medium bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white transition-all"
        >
          Add
        </button>
        <button
          @click="cancelAddPlayer"
          class="px-2 py-1.5 rounded-full text-xs text-emerald-500 hover:text-emerald-300 transition-colors"
          aria-label="Cancel"
        >
          ✕
        </button>
      </div>
    </div>
    <p v-if="addPlayerError" class="text-red-400 text-xs text-center -mt-1 mb-1 px-4">{{ addPlayerError }}</p>

    <!-- Map / Glass Toggle -->
    <div class="flex items-center justify-center py-2 shrink-0">
      <div class="flex bg-emerald-900/60 rounded-full p-0.5 border border-emerald-800/50">
        <button
          @click="viewMode = 'map'"
          :class="viewMode === 'map' ? 'bg-emerald-700 text-white shadow-sm' : 'text-emerald-500'"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/>
            <line x1="8" y1="2" x2="8" y2="18"/>
            <line x1="16" y1="6" x2="16" y2="22"/>
          </svg>
          Map
        </button>
        <button
          @click="viewMode = 'glass'; loadGlass3D()"
          :class="viewMode === 'glass' ? 'bg-emerald-700 text-white shadow-sm' : 'text-emerald-500'"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M8 2h8l1 10a5 5 0 01-10 0L8 2z"/>
            <path d="M12 17v5"/>
            <path d="M8 22h8"/>
          </svg>
          Glass
        </button>
      </div>
    </div>

    <!-- Course Map — inline pinch-zoomable (viewBox zoom = always crisp) -->
    <div
      v-if="viewMode === 'map' && game.courseMapSvg"
      ref="mapContainer"
      class="map-container"
      @touchstart.prevent="onMapTouchStart"
      @touchmove.prevent="onMapTouchMove"
      @touchend="onMapTouchEnd"
    >
      <div v-html="initialMapSvg" class="map-inner" />
      <div v-if="mapScale > 1.1" class="absolute top-1 right-1 bg-black/60 text-[9px] text-emerald-300 px-1.5 py-0.5 rounded">
        {{ Math.round(mapScale * 100) }}%
      </div>
    </div>

    <!-- 3D Glass View -->
    <GlassView3D
      v-if="viewMode === 'glass'"
      :glass-data="game.glass3dData"
      :scores="game.scores"
      :holes="game.holes"
      :glass-number="game.currentGlassNumber"
      :loading="game.glass3dLoading"
    />

    <!-- Scorecard Tables -->
    <div class="flex-1 py-2">
      <div v-for="(group, gi) in holeGroups" :key="gi" class="mb-3">
        <div class="text-[10px] uppercase tracking-wider text-emerald-600 mb-1 px-3">
          {{ holeGroups.length > 1 ? (gi === 0 ? 'OUT' : 'IN') : 'SCORE' }}
        </div>

        <!-- Horizontally scrollable table wrapper -->
        <div class="table-scroll-wrapper">
          <table class="scorecard-table">
            <thead>
              <tr class="bg-emerald-900">
                <th class="label-cell">Hole</th>
                <th
                  v-for="h in group" :key="h"
                  class="score-cell font-bold"
                  :class="h === game.currentHole ? 'bg-emerald-700 text-white' : 'text-emerald-300'"
                >{{ h }}</th>
                <th class="total-cell text-emerald-400">
                  {{ holeGroups.length > 1 ? (gi === 0 ? 'OUT' : 'IN') : 'TOT' }}
                </th>
              </tr>
            </thead>
            <tbody>
              <!-- Par -->
              <tr class="bg-emerald-900/60">
                <td class="label-cell text-emerald-500">Par</td>
                <td v-for="h in group" :key="h" class="score-cell text-emerald-400">{{ holeInfo(h).par }}</td>
                <td class="total-cell text-emerald-400 font-semibold">{{ groupPar(group) }}</td>
              </tr>
              <!-- Yards -->
              <tr class="bg-emerald-900/30">
                <td class="label-cell text-emerald-600">Yds</td>
                <td v-for="h in group" :key="h" class="score-cell text-emerald-600 text-[10px]">{{ holeInfo(h).yards || '-' }}</td>
                <td class="total-cell text-emerald-600 text-[10px]">{{ group.reduce((s, h) => s + (holeInfo(h).yards || 0), 0) }}</td>
              </tr>
              <!-- HCP -->
              <tr class="bg-emerald-900/20">
                <td class="label-cell text-emerald-600">Hcp</td>
                <td v-for="h in group" :key="h" class="score-cell text-emerald-700 text-[10px]">{{ holeInfo(h).handicap || '-' }}</td>
                <td class="total-cell"></td>
              </tr>
              <!-- Local players (all tappable) -->
              <tr
                v-for="(p, pi) in game.localPlayers"
                :key="p.playerId"
                :class="pi === game.activePlayerIndex ? 'bg-emerald-950' : 'bg-emerald-900/30'"
              >
                <td
                  class="label-cell font-bold truncate"
                  :class="pi === game.activePlayerIndex ? 'text-white bg-emerald-800' : 'text-emerald-300 bg-emerald-900/60'"
                >
                  {{ p.playerName.slice(0, 6) }}
                </td>
                <td
                  v-for="h in group" :key="h"
                  @click="openScoreInput(h, pi)"
                  class="score-cell cursor-pointer select-none active:scale-95 transition-all duration-150"
                  :class="[
                    p.scores[h] !== undefined ? scoreClass(p.scores[h], holeInfo(h).par) : 'hover:bg-emerald-800',
                    scoreFlash && scoreFlash.hole === h && scoreFlash.playerIndex === pi ? 'ring-2 ring-white' : '',
                  ]"
                >
                  <template v-if="p.scores[h] !== undefined">
                    <span class="font-bold">{{ p.scores[h] }}</span>
                  </template>
                  <template v-else>
                    <span class="text-emerald-700 text-lg leading-none">&middot;</span>
                  </template>
                </td>
                <td
                  class="total-cell font-bold"
                  :class="pi === game.activePlayerIndex ? 'bg-emerald-800/50' : 'bg-emerald-900/40 text-emerald-300'"
                >
                  {{ groupTotal(group, p.scores) || '-' }}
                </td>
              </tr>
              <!-- Remote players (read-only) -->
              <tr v-for="other in game.otherPlayers" :key="other.player_id" class="bg-emerald-900/15">
                <td class="label-cell text-emerald-500 truncate">
                  {{ other.player_name.slice(0, 6) }}
                </td>
                <td
                  v-for="h in group" :key="h"
                  class="score-cell text-[11px]"
                  :class="otherPlayerScore(other.player_id, h) !== undefined ? scoreClass(otherPlayerScore(other.player_id, h), holeInfo(h).par) + ' !bg-opacity-50' : ''"
                >
                  <template v-if="otherPlayerScore(other.player_id, h) !== undefined">
                    {{ otherPlayerScore(other.player_id, h) }}
                  </template>
                </td>
                <td class="total-cell text-emerald-500 text-[11px] font-medium">
                  {{ otherPlayerGroupTotal(other.player_id, group) || '-' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Grand totals (per local player) -->
      <div v-if="holeGroups.length > 1" class="mb-3 px-2">
        <table class="w-full border-collapse text-xs">
          <tbody>
            <tr
              v-for="(p, pi) in game.localPlayers"
              :key="p.playerId"
              :class="pi === game.activePlayerIndex ? 'bg-emerald-800' : 'bg-emerald-900/40'"
            >
              <td class="px-1.5 py-2 text-[10px] uppercase text-white font-bold border border-emerald-700 w-24 truncate">
                {{ p.playerName.slice(0, 10) }}
              </td>
              <td class="px-2 py-2 text-center border border-emerald-700">
                <span class="font-bold text-sm">{{ grandTotal(p.scores) }}</span>
                <span class="text-emerald-400 text-[10px] ml-1">({{ formatRelPar(playerCumulative(p.scores)) }})</span>
              </td>
              <td class="px-2 py-2 text-center text-emerald-400 border border-emerald-700 text-[10px]">
                Par {{ totalPar() }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Legend -->
      <div class="flex items-center justify-center gap-2 mt-1 mb-3 flex-wrap px-2">
        <div class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-amber-400"></span><span class="text-[9px] text-emerald-600">Eagle</span></div>
        <div class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-red-500"></span><span class="text-[9px] text-emerald-600">Birdie</span></div>
        <div class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-emerald-600"></span><span class="text-[9px] text-emerald-600">Par</span></div>
        <div class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-sky-400"></span><span class="text-[9px] text-emerald-600">Bogey</span></div>
        <div class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-sky-600"></span><span class="text-[9px] text-emerald-600">Dbl+</span></div>
      </div>

      <!-- Undo -->
      <div v-if="game.lastScoredHole" class="text-center mb-3">
        <button
          @click="game.undoLastScore()"
          class="px-4 py-2 rounded-lg text-xs text-gray-400 hover:text-gray-200 bg-emerald-900/30 border border-emerald-800/50 transition-colors"
        >
          Undo last score
        </button>
      </div>
    </div>

    <!-- Footer -->
    <footer class="px-4 py-3 bg-emerald-900/50 border-t border-emerald-800 shrink-0">
      <div class="flex items-center justify-center gap-3">
        <button
          @click="game.view = 'leaderboard'"
          class="px-5 py-2.5 rounded-xl bg-emerald-800/60 border border-emerald-700/50 text-emerald-300 text-sm font-medium hover:bg-emerald-700/60 transition-colors"
        >Leaderboard</button>
        <button
          @click="game.view = 'history'"
          class="px-5 py-2.5 rounded-xl bg-emerald-900/40 border border-emerald-700/50 text-emerald-400 text-sm hover:bg-emerald-800/40 transition-colors"
        >History</button>
        <button
          @click="handleNewGame"
          class="px-5 py-2.5 rounded-xl text-sm transition-colors"
          :class="confirmNewGame
            ? 'bg-red-700/60 border border-red-500/50 text-red-200 font-medium'
            : 'bg-emerald-900/40 border border-emerald-700/50 text-emerald-500 hover:bg-emerald-800/40'"
        >{{ confirmNewGame ? 'Confirm?' : 'New Game' }}</button>
      </div>
      <p class="text-center text-[9px] text-emerald-700 mt-2">Tap a hole to score &middot; Pinch map to zoom</p>
    </footer>

    <!-- Score Input Modal -->
    <div
      v-if="selectedHole !== null"
      class="fixed inset-0 bg-black/70 z-50 flex items-end justify-center"
      @click.self="closeModal"
    >
      <div class="bg-emerald-900 rounded-t-2xl w-full max-w-sm p-5 border-t border-x border-emerald-700 shadow-2xl safe-bottom">
        <div class="text-center mb-4">
          <div v-if="selectedPlayer" class="text-emerald-300 text-sm font-medium mb-1">
            Add score for <span class="text-white">{{ selectedPlayer.playerName }}</span>
          </div>
          <div class="text-emerald-400/70 text-xs">Glass {{ Math.ceil(selectedHole / game.holesPerGlass) }}</div>
          <div class="text-2xl font-bold">Hole {{ selectedHole }}</div>
          <div class="text-emerald-300 text-sm">
            Par {{ holeInfo(selectedHole).par }}
            <span v-if="holeInfo(selectedHole).yards"> &middot; {{ holeInfo(selectedHole).yards }}yd</span>
          </div>
        </div>
        <p class="text-xs text-emerald-400/80 text-center mb-2">Score (relative to par)</p>
        <div class="grid grid-cols-7 gap-2 mb-3">
          <button
            v-for="rel in scoreOptions" :key="rel"
            @click="handleScore(rel)"
            class="py-3.5 rounded-xl text-base font-bold transition-all duration-150 active:scale-95"
            :class="relToPar(scoreForSelectedHole(), holeInfo(selectedHole).par) === rel
              ? 'bg-emerald-500 text-white ring-2 ring-emerald-300'
              : 'bg-emerald-800/60 text-emerald-200 hover:bg-emerald-700 border border-emerald-700/50'"
          >{{ rel === 0 ? 'E' : rel > 0 ? `+${rel}` : `${rel}` }}</button>
        </div>
        <button
          @click="handlePenalty"
          class="w-full py-2.5 rounded-xl text-sm font-semibold bg-red-900/40 text-red-300 border border-red-800/50 hover:bg-red-900/60 transition-colors active:scale-[0.98]"
        >+8 Penalty</button>
        <button
          v-if="scoreForSelectedHole() !== undefined"
          @click="handleRemoveScore"
          class="w-full mt-2 py-2.5 rounded-xl text-sm font-medium bg-gray-800/60 text-gray-300 border border-gray-700/50 hover:bg-gray-700/60 transition-colors active:scale-[0.98]"
        >Remove Score</button>
        <button
          @click="closeModal"
          class="w-full mt-2 py-2 rounded-xl text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >Cancel</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scorecard-root {
  min-height: 100dvh;
  background: #022c22; /* emerald-950 */
  color: white;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
  max-width: 100vw;
  /* Block pinch-zoom on mobile; map container opts back in via touch-action: none */
  touch-action: pan-x pan-y;
}

/* Course map container — clips overflow, allows pinch-zoom inside */
.map-container {
  position: relative;
  overflow: hidden;
  margin: 8px;
  border-radius: 12px;
  border: 1px solid rgba(5, 150, 105, 0.3);
  background: rgba(6, 78, 59, 0.3);
  max-height: 200px;
  touch-action: none; /* we handle pinch ourselves */
}

.map-inner :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
}

/* Scorecard table — horizontally scrollable */
.table-scroll-wrapper {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  padding: 0 8px;
}

.scorecard-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  min-width: 420px; /* forces scroll on small screens */
}

.scorecard-table th,
.scorecard-table td {
  border: 1px solid rgba(5, 150, 105, 0.3);
  text-align: center;
  padding: 4px 3px;
}

.label-cell {
  text-align: left;
  padding: 4px 6px;
  font-size: 10px;
  text-transform: uppercase;
  font-weight: 500;
  width: 52px;
  min-width: 52px;
  max-width: 52px;
  position: sticky;
  left: 0;
  z-index: 1;
  background: #022c22;
}

.score-cell {
  min-width: 28px;
}

.total-cell {
  min-width: 36px;
  font-weight: 600;
}

/* Safe area for bottom sheet on notched phones */
.safe-bottom {
  padding-bottom: calc(20px + env(safe-area-inset-bottom, 0px));
}
</style>
