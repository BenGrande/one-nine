<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useGameStore } from '../stores/game'
import JoinGame from '../components/JoinGame.vue'
import ScoreCard from '../components/ScoreCard.vue'
import Leaderboard from '../components/Leaderboard.vue'
import GameHistory from '../components/GameHistory.vue'

const route = useRoute()
const game = useGameStore()

onMounted(async () => {
  const glassSetId = route.params.glassSetId as string
  const glassNumber = route.query.glass as string

  game.glassSetId = glassSetId
  if (glassNumber) game.glassNumber = parseInt(glassNumber) || 1

  // Try reconnection first
  const reconnected = await game.reconnect(glassSetId)
  if (!reconnected) {
    game.view = 'join'
  }
})
</script>

<template>
  <JoinGame v-if="game.view === 'join'" />
  <ScoreCard v-else-if="game.view === 'scorecard'" />
  <Leaderboard v-else-if="game.view === 'leaderboard'" />
  <GameHistory v-else-if="game.view === 'history'" />
</template>
