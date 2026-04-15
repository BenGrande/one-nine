<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '../stores/game'

const game = useGameStore()
const selectedHole = ref<number | null>(null)
const scoreFlash = ref<number | null>(null)
const mapExpanded = ref(false)

// Map zoom/pan state
const mapScale = ref(1)
const mapX = ref(0)
const mapY = ref(0)
let isPanning = false
let panStartX = 0
let panStartY = 0
let panStartMapX = 0
let panStartMapY = 0
let lastPinchDist = 0

function onMapPointerDown(e: PointerEvent) {
  isPanning = true
  panStartX = e.clientX
  panStartY = e.clientY
  panStartMapX = mapX.value
  panStartMapY = mapY.value
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}

function onMapPointerMove(e: PointerEvent) {
  if (!isPanning) return
  mapX.value = panStartMapX + (e.clientX - panStartX)
  mapY.value = panStartMapY + (e.clientY - panStartY)
}

function onMapPointerUp() {
  isPanning = false
}

function onMapWheel(e: WheelEvent) {
  e.preventDefault()
  const factor = e.deltaY < 0 ? 1.15 : 0.87
  mapScale.value = Math.max(0.5, Math.min(10, mapScale.value * factor))
}

function onMapTouchStart(e: TouchEvent) {
  if (e.touches.length === 2) {
    const dx = e.touches[0].clientX - e.touches[1].clientX
    const dy = e.touches[0].clientY - e.touches[1].clientY
    lastPinchDist = Math.hypot(dx, dy)
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
      mapScale.value = Math.max(0.5, Math.min(10, mapScale.value * factor))
    }
    lastPinchDist = dist
  }
}

function onMapTouchEnd() {
  lastPinchDist = 0
}

function toggleMapExpanded() {
  mapExpanded.value = !mapExpanded.value
  if (!mapExpanded.value) {
    mapScale.value = 1
    mapX.value = 0
    mapY.value = 0
  }
}

function resetMapZoom() {
  mapScale.value = 1
  mapX.value = 0
  mapY.value = 0
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

function playerScoreForHole(holeNum: number): number | undefined {
  return game.scores[holeNum]
}

function relToPar(score: number | undefined, par: number): number | null {
  if (score === undefined) return null
  return score - par
}

function scoreClass(score: number | undefined, par: number): string {
  if (score === undefined) return ''
  const rel = score - par
  if (rel <= -2) return 'bg-amber-400 text-amber-950 font-bold'       // Eagle+
  if (rel === -1) return 'bg-red-500 text-white font-bold'             // Birdie
  if (rel === 0) return 'bg-emerald-600 text-white'                    // Par
  if (rel === 1) return 'bg-sky-400 text-sky-950'                      // Bogey
  if (rel === 2) return 'bg-sky-600 text-white'                        // Double
  return 'bg-sky-800 text-white'                                       // Triple+
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

function formatRelPar(n: number): string {
  if (n === 0) return 'E'
  return n > 0 ? `+${n}` : `${n}`
}

// Score input
function openScoreInput(holeNum: number) {
  selectedHole.value = holeNum
}

function vibrate() {
  try { navigator.vibrate?.(30) } catch { /* not available */ }
}

async function handleScore(rel: number) {
  if (selectedHole.value === null) return
  const hole = selectedHole.value
  const par = holeInfo(hole).par
  const actual = par + rel
  const ok = await game.submitScore(hole, actual)
  if (ok !== false) {
    vibrate()
    scoreFlash.value = hole
    setTimeout(() => {
      scoreFlash.value = null
    }, 400)
    selectedHole.value = null
    // Auto-advance to next unscored
    game.advanceToNextUnscored()
  }
}

async function handlePenalty() {
  if (selectedHole.value === null) return
  const hole = selectedHole.value
  const par = holeInfo(hole).par
  await game.submitScore(hole, par + 8)
  vibrate()
  selectedHole.value = null
  game.advanceToNextUnscored()
}

function closeModal() {
  selectedHole.value = null
}

onMounted(() => {
  game.startScorePolling()
})

onUnmounted(() => {
  game.stopScorePolling()
})
</script>

<template>
  <div class="min-h-screen bg-emerald-950 text-white flex flex-col">
    <!-- Header -->
    <header class="bg-emerald-900 px-4 py-3 flex items-center justify-between shrink-0 border-b border-emerald-800">
      <div>
        <h1 class="text-lg font-bold tracking-tight">{{ game.courseName || 'One Nine' }}</h1>
        <p class="text-emerald-400 text-xs">{{ game.playerName }} &middot; Glass {{ game.currentGlassNumber }}</p>
      </div>
      <div class="text-right">
        <div class="text-2xl font-bold tabular-nums" :class="game.cumulativeScore < 0 ? 'text-red-400' : game.cumulativeScore === 0 ? 'text-emerald-300' : 'text-white'">
          {{ formatRelPar(game.cumulativeScore) }}
        </div>
        <div class="text-[10px] text-emerald-500">{{ game.holesScored }}/{{ game.totalHoles }} holes</div>
      </div>
    </header>

    <!-- Course Map (inline, tap to expand) -->
    <div v-if="game.courseMapSvg && !mapExpanded" class="px-2 pt-2">
      <div
        @click="toggleMapExpanded"
        class="w-full max-h-[160px] overflow-hidden rounded-xl border border-emerald-800/50 bg-emerald-900/30 cursor-pointer relative"
      >
        <div v-html="game.courseMapSvg" class="[&>svg]:w-full [&>svg]:h-auto [&>svg]:block" />
        <div class="absolute bottom-1 right-1 bg-black/50 text-[9px] text-emerald-300 px-1.5 py-0.5 rounded">
          Tap to expand
        </div>
      </div>
    </div>

    <!-- Course Map (fullscreen zoomable overlay) -->
    <div
      v-if="mapExpanded"
      class="fixed inset-0 z-50 bg-emerald-950 flex flex-col"
    >
      <!-- Map header -->
      <div class="flex items-center justify-between px-3 py-2 bg-emerald-900 border-b border-emerald-800 shrink-0">
        <span class="text-sm font-medium text-emerald-300">{{ game.courseName || 'Course Map' }}</span>
        <div class="flex items-center gap-2">
          <button
            @click="resetMapZoom"
            class="px-2 py-1 text-[10px] bg-emerald-800 border border-emerald-700 rounded text-emerald-400 hover:bg-emerald-700"
          >Reset</button>
          <button
            @click="toggleMapExpanded"
            class="px-2 py-1 text-xs bg-emerald-800 border border-emerald-700 rounded text-white hover:bg-emerald-700"
          >Close</button>
        </div>
      </div>

      <!-- Zoomable map area -->
      <div
        class="flex-1 overflow-hidden touch-none"
        @pointerdown="onMapPointerDown"
        @pointermove="onMapPointerMove"
        @pointerup="onMapPointerUp"
        @pointercancel="onMapPointerUp"
        @wheel.prevent="onMapWheel"
        @touchstart="onMapTouchStart"
        @touchmove="onMapTouchMove"
        @touchend="onMapTouchEnd"
      >
        <div
          class="w-full h-full flex items-center justify-center"
          :style="{
            transform: `translate(${mapX}px, ${mapY}px) scale(${mapScale})`,
            transformOrigin: 'center center',
            transition: isPanning ? 'none' : 'transform 0.15s ease-out',
          }"
        >
          <div v-html="game.courseMapSvg" class="[&>svg]:w-full [&>svg]:max-h-[80vh] [&>svg]:h-auto" />
        </div>
      </div>

      <!-- Zoom info -->
      <div class="px-3 py-1.5 bg-emerald-900 border-t border-emerald-800 text-[10px] text-emerald-600 text-center shrink-0">
        Pinch or scroll to zoom &middot; Drag to pan &middot; {{ Math.round(mapScale * 100) }}%
      </div>
    </div>

    <!-- Scorecard Tables -->
    <main class="flex-1 overflow-x-auto px-2 py-3">
      <div v-for="(group, gi) in holeGroups" :key="gi" class="mb-4">
        <!-- Section label -->
        <div class="text-[10px] uppercase tracking-wider text-emerald-600 mb-1 px-1">
          {{ holeGroups.length > 1 ? (gi === 0 ? 'OUT' : 'IN') : 'SCORE' }}
        </div>

        <div class="overflow-x-auto">
          <table class="w-full border-collapse text-xs min-w-[500px]">
            <!-- Hole numbers -->
            <thead>
              <tr class="bg-emerald-900">
                <th class="px-1.5 py-1.5 text-left text-[10px] uppercase text-emerald-500 font-medium w-16 border border-emerald-800">Hole</th>
                <th
                  v-for="h in group" :key="h"
                  class="px-1 py-1.5 text-center font-bold border border-emerald-800 min-w-[32px]"
                  :class="h === game.currentHole ? 'bg-emerald-700 text-white' : 'text-emerald-300'"
                >{{ h }}</th>
                <th class="px-1.5 py-1.5 text-center font-bold text-emerald-400 border border-emerald-800 min-w-[40px]">
                  {{ holeGroups.length > 1 ? (gi === 0 ? 'OUT' : 'IN') : 'TOT' }}
                </th>
              </tr>
            </thead>

            <tbody>
              <!-- Par row -->
              <tr class="bg-emerald-900/60">
                <td class="px-1.5 py-1 text-[10px] uppercase text-emerald-500 font-medium border border-emerald-800">Par</td>
                <td v-for="h in group" :key="h" class="px-1 py-1 text-center text-emerald-400 border border-emerald-800">{{ holeInfo(h).par }}</td>
                <td class="px-1 py-1 text-center text-emerald-400 font-semibold border border-emerald-800">{{ groupPar(group) }}</td>
              </tr>

              <!-- Yards row -->
              <tr class="bg-emerald-900/30">
                <td class="px-1.5 py-1 text-[10px] uppercase text-emerald-600 font-medium border border-emerald-800">Yds</td>
                <td v-for="h in group" :key="h" class="px-1 py-1 text-center text-emerald-600 text-[10px] border border-emerald-800">{{ holeInfo(h).yards || '-' }}</td>
                <td class="px-1 py-1 text-center text-emerald-600 text-[10px] border border-emerald-800">{{ group.reduce((s, h) => s + (holeInfo(h).yards || 0), 0) }}</td>
              </tr>

              <!-- HCP row -->
              <tr class="bg-emerald-900/20">
                <td class="px-1.5 py-1 text-[10px] uppercase text-emerald-600 font-medium border border-emerald-800">Hcp</td>
                <td v-for="h in group" :key="h" class="px-1 py-1 text-center text-emerald-700 text-[10px] border border-emerald-800">{{ holeInfo(h).handicap || '-' }}</td>
                <td class="px-1 py-1 border border-emerald-800"></td>
              </tr>

              <!-- Current player score row -->
              <tr class="bg-emerald-950">
                <td class="px-1.5 py-1.5 text-[10px] uppercase text-white font-bold border border-emerald-700 bg-emerald-800">
                  {{ game.playerName.slice(0, 6) }}
                </td>
                <td
                  v-for="h in group" :key="h"
                  @click="openScoreInput(h)"
                  class="px-1 py-1.5 text-center border border-emerald-700 cursor-pointer transition-all duration-150 select-none active:scale-95"
                  :class="[
                    playerScoreForHole(h) !== undefined ? scoreClass(playerScoreForHole(h), holeInfo(h).par) : 'hover:bg-emerald-800',
                    scoreFlash === h ? 'ring-2 ring-white' : '',
                  ]"
                >
                  <template v-if="playerScoreForHole(h) !== undefined">
                    <span class="font-bold">{{ playerScoreForHole(h) }}</span>
                  </template>
                  <template v-else>
                    <span class="text-emerald-700 text-lg leading-none">&middot;</span>
                  </template>
                </td>
                <td class="px-1 py-1.5 text-center font-bold border border-emerald-700 bg-emerald-800/50">
                  {{ groupTotal(group, game.scores) || '-' }}
                </td>
              </tr>

              <!-- Other players -->
              <tr
                v-for="other in game.otherPlayers" :key="other.player_id"
                class="bg-emerald-900/15"
              >
                <td class="px-1.5 py-1 text-[10px] text-emerald-500 border border-emerald-800 truncate max-w-[60px]">
                  {{ other.player_name.slice(0, 6) }}
                </td>
                <td
                  v-for="h in group" :key="h"
                  class="px-1 py-1 text-center border border-emerald-800/50 text-[11px]"
                  :class="otherPlayerScore(other.player_id, h) !== undefined ? scoreClass(otherPlayerScore(other.player_id, h), holeInfo(h).par) + ' !bg-opacity-50' : ''"
                >
                  <template v-if="otherPlayerScore(other.player_id, h) !== undefined">
                    {{ otherPlayerScore(other.player_id, h) }}
                  </template>
                </td>
                <td class="px-1 py-1 text-center text-emerald-500 text-[11px] font-medium border border-emerald-800/50">
                  {{ otherPlayerGroupTotal(other.player_id, group) || '-' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Grand totals (when split into OUT/IN) -->
      <div v-if="holeGroups.length > 1" class="mb-4">
        <table class="w-full border-collapse text-xs">
          <tbody>
            <tr class="bg-emerald-800">
              <td class="px-1.5 py-2 text-[10px] uppercase text-white font-bold border border-emerald-700 w-16">Total</td>
              <td class="px-2 py-2 text-center border border-emerald-700">
                <span class="font-bold text-sm">{{ grandTotal(game.scores) }}</span>
                <span class="text-emerald-400 text-[10px] ml-1">({{ formatRelPar(game.cumulativeScore) }})</span>
              </td>
              <td class="px-2 py-2 text-center text-emerald-400 border border-emerald-700 text-[10px]">
                Par {{ totalPar() }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Score Legend -->
      <div class="flex items-center justify-center gap-2 mt-2 mb-4 flex-wrap">
        <div class="flex items-center gap-1">
          <span class="w-3 h-3 rounded-sm bg-amber-400"></span>
          <span class="text-[9px] text-emerald-600">Eagle</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-3 rounded-sm bg-red-500"></span>
          <span class="text-[9px] text-emerald-600">Birdie</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-3 rounded-sm bg-emerald-600"></span>
          <span class="text-[9px] text-emerald-600">Par</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-3 rounded-sm bg-sky-400"></span>
          <span class="text-[9px] text-emerald-600">Bogey</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-3 rounded-sm bg-sky-600"></span>
          <span class="text-[9px] text-emerald-600">Dbl+</span>
        </div>
      </div>

      <!-- Undo -->
      <div v-if="game.lastScoredHole" class="text-center mb-4">
        <button
          @click="game.undoLastScore()"
          class="px-4 py-2 rounded-lg text-xs text-gray-400 hover:text-gray-200 bg-emerald-900/30 border border-emerald-800/50 transition-colors"
        >
          Undo last score
        </button>
      </div>
    </main>

    <!-- Footer -->
    <footer class="px-4 py-3 bg-emerald-900/50 border-t border-emerald-800 shrink-0">
      <div class="flex items-center justify-center gap-3 max-w-lg mx-auto">
        <button
          @click="game.view = 'leaderboard'"
          class="px-5 py-2.5 rounded-xl bg-emerald-800/60 border border-emerald-700/50 text-emerald-300 text-sm font-medium hover:bg-emerald-700/60 transition-colors"
        >
          Leaderboard
        </button>
        <button
          @click="game.view = 'history'"
          class="px-5 py-2.5 rounded-xl bg-emerald-900/40 border border-emerald-700/50 text-emerald-400 text-sm hover:bg-emerald-800/40 transition-colors"
        >
          History
        </button>
      </div>
      <p class="text-center text-[9px] text-emerald-700 mt-2">Tap a hole cell to enter score &middot; Auto-syncs every 10s</p>
    </footer>

    <!-- Score Input Modal -->
    <div
      v-if="selectedHole !== null"
      class="fixed inset-0 bg-black/70 z-50 flex items-end sm:items-center justify-center"
      @click.self="closeModal"
    >
      <div class="bg-emerald-900 rounded-t-2xl sm:rounded-2xl w-full max-w-sm p-5 border border-emerald-700 shadow-2xl">
        <!-- Hole info -->
        <div class="text-center mb-4">
          <div class="text-emerald-400/70 text-xs">Glass {{ Math.ceil(selectedHole / game.holesPerGlass) }}</div>
          <div class="text-2xl font-bold">Hole {{ selectedHole }}</div>
          <div class="text-emerald-300 text-sm">
            Par {{ holeInfo(selectedHole).par }}
            <span v-if="holeInfo(selectedHole).yards"> &middot; {{ holeInfo(selectedHole).yards }}yd</span>
          </div>
        </div>

        <!-- Score buttons -->
        <p class="text-xs text-emerald-400/80 text-center mb-2">Score (relative to par)</p>
        <div class="grid grid-cols-7 gap-2 mb-3">
          <button
            v-for="rel in scoreOptions"
            :key="rel"
            @click="handleScore(rel)"
            class="py-3.5 rounded-xl text-base font-bold transition-all duration-150 active:scale-95"
            :class="relToPar(playerScoreForHole(selectedHole), holeInfo(selectedHole).par) === rel
              ? 'bg-emerald-500 text-white ring-2 ring-emerald-300'
              : 'bg-emerald-800/60 text-emerald-200 hover:bg-emerald-700 border border-emerald-700/50'"
          >
            {{ rel === 0 ? 'E' : rel > 0 ? `+${rel}` : `${rel}` }}
          </button>
        </div>
        <button
          @click="handlePenalty"
          class="w-full py-2.5 rounded-xl text-sm font-semibold bg-red-900/40 text-red-300 border border-red-800/50 hover:bg-red-900/60 transition-colors active:scale-[0.98]"
        >
          +8 Penalty
        </button>
        <button
          @click="closeModal"
          class="w-full mt-2 py-2 rounded-xl text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>
