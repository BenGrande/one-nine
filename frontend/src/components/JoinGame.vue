<script setup lang="ts">
import { ref } from 'vue'
import { useGameStore } from '../stores/game'

const game = useGameStore()
const name = ref('')
const error = ref('')
const hasJoinedFirst = ref(false)

async function handleJoin() {
  if (!name.value.trim()) {
    error.value = 'Please enter your name'
    return
  }
  error.value = ''

  if (!hasJoinedFirst.value) {
    // First player — creates/finds session
    const ok = await game.joinGame(game.glassSetId, name.value.trim())
    if (!ok) {
      error.value = 'Could not join game. Please try again.'
      return
    }
    hasJoinedFirst.value = true
    name.value = ''
  } else {
    // Additional player — joins existing session
    const ok = await game.addPlayer(name.value.trim())
    if (!ok) {
      error.value = 'Could not add player. Please try again.'
      return
    }
    name.value = ''
  }
}

function startPlaying() {
  game.view = 'scorecard'
  game.startScorePolling()
}
</script>

<template>
  <div class="min-h-screen bg-emerald-950 text-white flex flex-col items-center justify-center p-6">
    <!-- Branding -->
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold tracking-tight mb-2">Split the Tee</h1>
      <p v-if="game.courseName" class="text-emerald-300 text-lg">{{ game.courseName }}</p>
      <p v-else class="text-emerald-400/60 text-sm">Golf Score Keeper</p>
    </div>

    <!-- Join Form -->
    <div class="w-full max-w-sm">
      <div class="bg-emerald-900/50 rounded-2xl p-6 border border-emerald-800/50">
        <!-- Players already added -->
        <div v-if="game.localPlayers.length > 0" class="mb-4">
          <p class="text-xs text-emerald-500 uppercase tracking-wider mb-2">Players</p>
          <div class="space-y-1.5">
            <div
              v-for="(p, i) in game.localPlayers"
              :key="p.playerId"
              class="flex items-center gap-2 px-3 py-2 bg-emerald-800/40 rounded-lg"
            >
              <span class="text-emerald-400 text-xs font-bold w-5">{{ i + 1 }}</span>
              <span class="text-white text-sm font-medium">{{ p.playerName }}</span>
            </div>
          </div>
        </div>

        <label class="block text-sm text-emerald-300 mb-2 font-medium">
          {{ hasJoinedFirst ? 'Add Another Player' : 'Your Name' }}
        </label>
        <input
          v-model="name"
          type="text"
          :placeholder="hasJoinedFirst ? 'Enter player name' : 'Enter your name'"
          autofocus
          @keydown.enter="handleJoin"
          class="w-full px-4 py-3 bg-emerald-900 border border-emerald-700 rounded-xl text-white text-lg placeholder-emerald-600 focus:outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400"
        />
        <p v-if="error" class="text-red-400 text-sm mt-2">{{ error }}</p>

        <!-- Before first join: single button -->
        <button
          v-if="!hasJoinedFirst"
          @click="handleJoin"
          :disabled="game.loading"
          class="w-full mt-4 px-4 py-3.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-lg font-semibold transition-colors"
        >
          <span v-if="game.loading" class="inline-flex items-center gap-2">
            <span class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Joining...
          </span>
          <span v-else>Join Game</span>
        </button>

        <!-- After first join: Add Another + Start Playing -->
        <div v-else class="mt-4 space-y-2">
          <button
            @click="handleJoin"
            :disabled="game.loading"
            class="w-full px-4 py-3 bg-emerald-800/60 hover:bg-emerald-700/60 border border-emerald-700/50 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-sm font-medium transition-colors text-emerald-300"
          >
            <span v-if="game.loading" class="inline-flex items-center gap-2">
              <span class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Adding...
            </span>
            <span v-else>Add Player</span>
          </button>
          <button
            @click="startPlaying"
            class="w-full px-4 py-3.5 bg-emerald-600 hover:bg-emerald-500 rounded-xl text-lg font-semibold transition-colors"
          >
            Start Playing
          </button>
        </div>
      </div>

      <!-- History link -->
      <button
        @click="game.view = 'history'"
        class="mt-4 text-emerald-600 text-xs hover:text-emerald-400 transition-colors"
      >
        View previous games
      </button>
    </div>
  </div>
</template>
