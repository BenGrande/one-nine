<script setup lang="ts">
import { useGameStore } from '../stores/game'

const game = useGameStore()

async function handleStartNew() {
  await game.startNewGame()
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

    <!-- Choice Card -->
    <div class="w-full max-w-sm">
      <div class="bg-emerald-900/50 rounded-2xl p-6 border border-emerald-800/50">
        <!-- Active session info -->
        <div v-if="game.activeSessionInfo" class="text-center mb-5">
          <p class="text-emerald-300 text-sm">
            There's an active game with
            <span class="font-semibold text-white">{{ game.activeSessionInfo.playerCount }}</span>
            player{{ game.activeSessionInfo.playerCount === 1 ? '' : 's' }}
          </p>
        </div>

        <button
          @click="game.view = 'join'"
          class="w-full px-4 py-3.5 bg-emerald-600 hover:bg-emerald-500 rounded-xl text-lg font-semibold transition-colors"
        >
          Join Existing Game
        </button>

        <div class="flex items-center gap-3 my-4">
          <div class="flex-1 h-px bg-emerald-800"></div>
          <span class="text-emerald-600 text-xs uppercase tracking-wider">or</span>
          <div class="flex-1 h-px bg-emerald-800"></div>
        </div>

        <button
          @click="handleStartNew"
          :disabled="game.loading"
          class="w-full px-4 py-3.5 bg-emerald-900/60 hover:bg-emerald-800/60 border border-emerald-700/50 rounded-xl text-lg font-semibold transition-colors text-emerald-300"
        >
          Start New Game
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
