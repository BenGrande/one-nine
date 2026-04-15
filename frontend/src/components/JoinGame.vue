<script setup lang="ts">
import { ref } from 'vue'
import { useGameStore } from '../stores/game'

const game = useGameStore()
const name = ref('')
const error = ref('')

async function handleJoin() {
  if (!name.value.trim()) {
    error.value = 'Please enter your name'
    return
  }
  error.value = ''
  const ok = await game.joinGame(game.glassSetId, name.value.trim())
  if (!ok) {
    error.value = 'Could not join game. Please try again.'
  }
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
        <label class="block text-sm text-emerald-300 mb-2 font-medium">Your Name</label>
        <input
          v-model="name"
          type="text"
          placeholder="Enter your name"
          autofocus
          @keydown.enter="handleJoin"
          class="w-full px-4 py-3 bg-emerald-900 border border-emerald-700 rounded-xl text-white text-lg placeholder-emerald-600 focus:outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400"
        />
        <p v-if="error" class="text-red-400 text-sm mt-2">{{ error }}</p>
        <button
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
