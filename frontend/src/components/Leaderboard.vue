<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useGameStore } from '../stores/game'

const game = useGameStore()

let refreshInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  game.fetchLeaderboard()
  refreshInterval = setInterval(() => {
    game.fetchLeaderboard()
  }, 10000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})

function formatScore(scoreToPar: number): string {
  if (scoreToPar === 0) return 'E'
  return scoreToPar > 0 ? `+${scoreToPar}` : `${scoreToPar}`
}

function medal(index: number): string {
  if (index === 0) return '\uD83E\uDD47'
  if (index === 1) return '\uD83E\uDD48'
  if (index === 2) return '\uD83E\uDD49'
  return ''
}

function isCurrentPlayer(entry: any): boolean {
  return entry.player_id === game.playerId
}

function currentPlayerPosition(): string {
  const idx = game.leaderboard.findIndex(e => e.player_id === game.playerId)
  if (idx < 0) return ''
  const pos = idx + 1
  const suffix = pos === 1 ? 'st' : pos === 2 ? 'nd' : pos === 3 ? 'rd' : 'th'
  return `${pos}${suffix}`
}
</script>

<template>
  <div class="min-h-screen bg-emerald-950 text-white flex flex-col">
    <!-- Header -->
    <header class="bg-emerald-900 px-4 py-3 shrink-0">
      <h2 class="text-lg font-bold">Leaderboard</h2>
      <p class="text-emerald-400 text-xs">{{ game.courseName }}</p>
    </header>

    <!-- Leaderboard List -->
    <main class="flex-1 px-4 py-4 max-w-lg mx-auto w-full">
      <div v-if="game.leaderboard.length === 0" class="text-center text-emerald-500 py-12">
        <p class="text-sm">No scores yet</p>
        <p class="text-xs mt-1 text-emerald-600">Scores will appear as players submit them</p>
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="(entry, idx) in game.leaderboard"
          :key="entry.player_id"
          class="flex items-center gap-3 px-4 py-3 rounded-xl transition-colors"
          :class="isCurrentPlayer(entry)
            ? 'bg-emerald-700/40 border border-emerald-500/50'
            : 'bg-emerald-900/40 border border-emerald-800/30'"
        >
          <!-- Rank -->
          <div class="w-8 text-center shrink-0">
            <span v-if="idx < 3" class="text-lg">{{ medal(idx) }}</span>
            <span v-else class="text-sm text-emerald-500">{{ idx + 1 }}</span>
          </div>

          <!-- Name -->
          <div class="flex-1 min-w-0">
            <div class="font-medium text-sm truncate" :class="isCurrentPlayer(entry) ? 'text-emerald-200' : 'text-white'">
              {{ entry.player_name }}
              <span v-if="isCurrentPlayer(entry)" class="text-emerald-400 text-xs">(you)</span>
            </div>
            <div class="text-[10px] text-emerald-500">{{ entry.holes_played }} holes</div>
          </div>

          <!-- Score -->
          <div
            class="text-lg font-bold tabular-nums"
            :class="entry.score_to_par < 0 ? 'text-red-400' : entry.score_to_par === 0 ? 'text-emerald-300' : 'text-white'"
          >
            {{ formatScore(entry.score_to_par) }}
          </div>
        </div>
      </div>

      <!-- Summary -->
      <div v-if="game.leaderboard.length > 0" class="mt-6 text-center text-xs text-emerald-500">
        <p>{{ game.holesScored }}/{{ game.totalHoles }} holes played</p>
        <p v-if="currentPlayerPosition()" class="mt-1">Your position: <span class="text-emerald-300 font-medium">{{ currentPlayerPosition() }}</span></p>
        <button
          @click="game.shareLeaderboard()"
          class="mt-3 px-4 py-2 rounded-lg bg-emerald-900/60 border border-emerald-700/50 text-emerald-400 text-xs hover:bg-emerald-800/60 transition-colors"
          aria-label="Copy leaderboard to clipboard"
        >
          Share Leaderboard
        </button>
        <p class="mt-2 text-emerald-600">Auto-refreshes every 10 seconds</p>
      </div>
    </main>

    <!-- Footer -->
    <footer class="px-4 py-4 shrink-0">
      <div class="flex items-center justify-center gap-3 max-w-lg mx-auto">
        <button
          @click="game.view = 'scorecard'"
          class="flex-1 px-4 py-3 rounded-xl bg-emerald-900/60 border border-emerald-700/50 text-emerald-300 text-sm font-medium text-center hover:bg-emerald-800/60 transition-colors"
        >
          Back to Scorecard
        </button>
        <button
          @click="game.view = 'history'"
          class="px-4 py-3 rounded-xl bg-emerald-900/40 border border-emerald-700/50 text-emerald-400 text-sm hover:bg-emerald-800/40 transition-colors"
        >
          History
        </button>
      </div>
    </footer>
  </div>
</template>
