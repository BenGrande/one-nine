<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useGameStore } from '../stores/game'

const game = useGameStore()
const confirmDelete = ref<string | null>(null)

onMounted(() => {
  game.fetchGameHistory()
})

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
      + ' ' + d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  } catch {
    return iso
  }
}

async function handleDelete(sessionId: string) {
  if (confirmDelete.value !== sessionId) {
    confirmDelete.value = sessionId
    return
  }
  await game.deleteGame(sessionId)
  confirmDelete.value = null
}

function formatScore(total: number): string {
  return String(total)
}
</script>

<template>
  <div class="min-h-screen bg-emerald-950 text-white flex flex-col">
    <!-- Header -->
    <header class="bg-emerald-900 px-4 py-3 shrink-0 border-b border-emerald-800">
      <h2 class="text-lg font-bold">Game History</h2>
      <p class="text-emerald-400 text-xs">{{ game.courseName || 'Split the Tee' }}</p>
    </header>

    <!-- History List -->
    <main class="flex-1 px-4 py-4 max-w-lg mx-auto w-full">
      <div v-if="game.gameHistory.length === 0" class="text-center text-emerald-500 py-12">
        <p class="text-sm">No games played yet</p>
        <p class="text-xs mt-1 text-emerald-600">Games will appear here after they are played</p>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="entry in game.gameHistory"
          :key="entry.session_id"
          class="bg-emerald-900/40 border border-emerald-800/50 rounded-xl p-4"
        >
          <!-- Game header -->
          <div class="flex items-center justify-between mb-2">
            <div>
              <div class="text-sm font-medium text-white">
                {{ formatDate(entry.created_at) }}
              </div>
              <div class="text-[10px] text-emerald-500">
                {{ entry.player_count }} player{{ entry.player_count !== 1 ? 's' : '' }}
                <span v-if="entry.active" class="text-emerald-400 ml-1">Active</span>
              </div>
            </div>
            <button
              @click="handleDelete(entry.session_id)"
              class="px-3 py-1.5 rounded-lg text-xs transition-colors"
              :class="confirmDelete === entry.session_id
                ? 'bg-red-600 text-white hover:bg-red-500'
                : 'bg-emerald-900/60 text-red-400 border border-red-900/50 hover:bg-red-900/30'"
            >
              {{ confirmDelete === entry.session_id ? 'Confirm?' : 'Delete' }}
            </button>
          </div>

          <!-- Players & scores -->
          <div v-if="entry.players.length > 0" class="space-y-1">
            <div
              v-for="(p, i) in entry.players"
              :key="p.player_id"
              class="flex items-center justify-between text-xs px-2 py-1 rounded"
              :class="i === 0 && entry.players.length > 1 ? 'bg-emerald-800/30' : ''"
            >
              <span class="text-emerald-300">
                <span v-if="i === 0 && entry.players.length > 1" class="mr-1">&#x1F3C6;</span>
                {{ p.player_name }}
              </span>
              <span class="text-emerald-400 tabular-nums">
                {{ formatScore(p.total_score) }}
                <span class="text-emerald-600 text-[10px] ml-1">({{ p.holes_played }} holes)</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Back Button -->
    <footer class="px-4 py-4 shrink-0">
      <button
        @click="game.view = game.sessionId ? 'scorecard' : 'join'"
        class="w-full max-w-lg mx-auto block px-4 py-3 rounded-xl bg-emerald-900/60 border border-emerald-700/50 text-emerald-300 text-sm font-medium text-center hover:bg-emerald-800/60 transition-colors"
      >
        {{ game.sessionId ? 'Back to Scorecard' : 'Back' }}
      </button>
    </footer>
  </div>
</template>
