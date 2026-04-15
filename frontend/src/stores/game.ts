import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Glass3DData } from '../types/glass3d'

export interface LeaderboardEntry {
  player_id: string
  player_name: string
  total_score: number
  holes_played: number
  score_to_par: number
  scores_by_hole: { hole_number: number; score: number }[]
}

export interface GameHistoryEntry {
  session_id: string
  course_name: string
  active: boolean
  created_at: string
  player_count: number
  players: { player_id: string; player_name: string; total_score: number; holes_played: number }[]
}

export const useGameStore = defineStore('game', () => {
  const glassSetId = ref('')
  const glassNumber = ref(1)
  const sessionId = ref<string | null>(null)
  const playerId = ref<string | null>(null)
  const playerName = ref('')
  const courseName = ref('')
  const glassCount = ref(3)
  const holesPerGlass = ref(6)
  const holes = ref<{ number: number; par: number; yards: number; handicap: number }[]>([])
  const courseMapSvg = ref('')
  const currentHole = ref(1)
  const scores = ref<Record<number, number>>({})
  const leaderboard = ref<LeaderboardEntry[]>([])
  const otherPlayers = ref<LeaderboardEntry[]>([])
  const gameHistory = ref<GameHistoryEntry[]>([])
  const loading = ref(false)
  const connected = ref(false)
  const view = ref<'join' | 'scorecard' | 'leaderboard' | 'history'>('join')
  const glass3dData = ref<Glass3DData | null>(null)
  const glass3dLoading = ref(false)

  const totalHoles = computed(() => glassCount.value * holesPerGlass.value)

  const currentHoleInfo = computed(() => {
    return holes.value.find(h => h.number === currentHole.value) || {
      number: currentHole.value,
      par: 4,
      yards: 0,
      handicap: 0,
    }
  })

  const currentGlassNumber = computed(() => {
    if (holesPerGlass.value <= 0) return 1
    return Math.ceil(currentHole.value / holesPerGlass.value)
  })

  const cumulativeScore = computed(() => {
    let total = 0
    for (const [hole, score] of Object.entries(scores.value)) {
      const holeInfo = holes.value.find(h => h.number === Number(hole))
      const par = holeInfo?.par || 4
      total += score - par
    }
    return total
  })

  const holesScored = computed(() => Object.keys(scores.value).length)

  function storageKey(): string {
    return `splitthetee_session_${glassSetId.value}`
  }

  function saveToStorage() {
    if (!sessionId.value || !playerId.value) return
    try {
      localStorage.setItem(storageKey(), JSON.stringify({
        sessionId: sessionId.value,
        playerId: playerId.value,
        playerName: playerName.value,
      }))
    } catch { /* localStorage may be unavailable */ }
  }

  function loadFromStorage(): { sessionId: string; playerId: string; playerName: string } | null {
    try {
      const data = localStorage.getItem(storageKey())
      if (!data) return null
      return JSON.parse(data)
    } catch {
      return null
    }
  }

  async function joinGame(setId: string, name: string) {
    glassSetId.value = setId
    playerName.value = name
    loading.value = true

    try {
      const res = await fetch('/api/v1/games/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ glass_set_id: setId, player_name: name }),
      })

      if (!res.ok) {
        loading.value = false
        return false
      }

      const data = await res.json()
      sessionId.value = data.session_id
      playerId.value = data.player_id
      courseName.value = data.course_name || ''
      glassCount.value = data.glass_count || 3
      holesPerGlass.value = data.holes_per_glass || 6
      holes.value = data.holes || []
      courseMapSvg.value = data.course_map_svg || ''

      if (data.scores) {
        for (const s of data.scores) {
          scores.value[s.hole_number] = s.score
        }
      }

      connected.value = true
      saveToStorage()
      view.value = 'scorecard'

      // Start polling for other players' scores
      startScorePolling()

      return true
    } catch {
      return false
    } finally {
      loading.value = false
    }
  }

  async function reconnect(setId: string) {
    glassSetId.value = setId
    const stored = loadFromStorage()
    if (!stored) return false

    loading.value = true
    try {
      const res = await fetch(
        `/api/v1/games/${stored.sessionId}/status?player_id=${stored.playerId}`
      )
      if (!res.ok) {
        localStorage.removeItem(storageKey())
        return false
      }

      const data = await res.json()
      sessionId.value = stored.sessionId
      playerId.value = stored.playerId
      playerName.value = stored.playerName
      courseName.value = data.course_name || ''
      glassCount.value = data.glass_count || 3
      holesPerGlass.value = data.holes_per_glass || 6
      holes.value = data.holes || []
      courseMapSvg.value = data.course_map_svg || ''

      if (data.scores) {
        for (const s of data.scores) {
          scores.value[s.hole_number] = s.score
        }
      }

      connected.value = true
      view.value = 'scorecard'

      // Start polling for other players' scores
      startScorePolling()

      return true
    } catch {
      return false
    } finally {
      loading.value = false
    }
  }

  async function submitScore(holeNumber: number, score: number) {
    if (!sessionId.value) return false

    // Track for undo
    lastScoredHole.value = { hole: holeNumber, score: scores.value[holeNumber] }
    // Optimistic update
    scores.value = { ...scores.value, [holeNumber]: score }

    try {
      const res = await fetch(`/api/v1/games/${sessionId.value}/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_id: playerId.value,
          hole_number: holeNumber,
          glass_number: Math.ceil(holeNumber / holesPerGlass.value),
          score,
        }),
      })

      return res.ok
    } catch {
      return false
    }
  }

  async function removeScore(holeNumber: number) {
    if (!sessionId.value || !playerId.value) return false

    // Optimistic update
    const oldScore = scores.value[holeNumber]
    const updated = { ...scores.value }
    delete updated[holeNumber]
    scores.value = updated

    try {
      const res = await fetch(
        `/api/v1/games/${sessionId.value}/score?player_id=${playerId.value}&hole_number=${holeNumber}`,
        { method: 'DELETE' },
      )
      if (!res.ok) {
        // Revert
        if (oldScore !== undefined) scores.value = { ...scores.value, [holeNumber]: oldScore }
        return false
      }
      return true
    } catch {
      if (oldScore !== undefined) scores.value = { ...scores.value, [holeNumber]: oldScore }
      return false
    }
  }

  async function fetchLeaderboard() {
    if (!sessionId.value) return

    try {
      const res = await fetch(`/api/v1/games/${sessionId.value}/leaderboard`)
      if (!res.ok) return
      const data = await res.json()
      const entries: LeaderboardEntry[] = (data.leaderboard || []).map((e: any) => ({
        ...e,
        score_to_par: e.score_to_par ?? 0,
      }))
      leaderboard.value = entries

      // Extract other players' scores (not the current player)
      otherPlayers.value = entries.filter(e => e.player_id !== playerId.value)
    } catch {
      // Silently fail
    }
  }

  // Score polling
  let scoreInterval: ReturnType<typeof setInterval> | null = null

  function startScorePolling() {
    stopScorePolling()
    fetchLeaderboard()
    scoreInterval = setInterval(fetchLeaderboard, 10000)
  }

  function stopScorePolling() {
    if (scoreInterval) {
      clearInterval(scoreInterval)
      scoreInterval = null
    }
  }

  async function fetchGameHistory() {
    if (!glassSetId.value) return
    try {
      const res = await fetch(`/api/v1/games/glass-set/${glassSetId.value}/history`)
      if (!res.ok) return
      const data = await res.json()
      gameHistory.value = data.history || []
    } catch {
      // Silently fail
    }
  }

  async function deleteGame(deleteSessionId: string) {
    try {
      const res = await fetch(`/api/v1/games/${deleteSessionId}`, { method: 'DELETE' })
      if (res.ok) {
        gameHistory.value = gameHistory.value.filter(g => g.session_id !== deleteSessionId)
      }
      return res.ok
    } catch {
      return false
    }
  }

  async function endGame() {
    if (!sessionId.value) return false
    try {
      const res = await fetch(`/api/v1/games/${sessionId.value}/end`, { method: 'POST' })
      return res.ok
    } catch {
      return false
    }
  }

  function nextHole() {
    if (currentHole.value < totalHoles.value) {
      currentHole.value++
    }
  }

  function prevHole() {
    if (currentHole.value > 1) {
      currentHole.value--
    }
  }

  // Undo support
  const lastScoredHole = ref<{ hole: number; score: number | undefined } | null>(null)

  function undoLastScore() {
    if (!lastScoredHole.value) return
    const { hole, score } = lastScoredHole.value
    const updated = { ...scores.value }
    if (score === undefined) {
      delete updated[hole]
    } else {
      updated[hole] = score
    }
    scores.value = updated
    currentHole.value = hole
    lastScoredHole.value = null
  }

  function shareLeaderboard(): string {
    if (leaderboard.value.length === 0) return ''
    let text = `Split the Tee — ${courseName.value}\n`
    text += '—'.repeat(30) + '\n'
    leaderboard.value.forEach((e, i) => {
      const medal = i === 0 ? '\uD83E\uDD47' : i === 1 ? '\uD83E\uDD48' : i === 2 ? '\uD83E\uDD49' : `${i + 1}.`
      const scoreToPar = e.score_to_par === 0 ? 'E' : e.score_to_par > 0 ? `+${e.score_to_par}` : `${e.score_to_par}`
      text += `${medal} ${e.player_name}  ${scoreToPar}  (${e.holes_played} holes)\n`
    })
    try {
      navigator.clipboard.writeText(text)
    } catch { /* clipboard may not be available */ }
    return text
  }

  async function fetchGlass3DData() {
    if (!sessionId.value || glass3dLoading.value) return
    glass3dLoading.value = true
    try {
      const res = await fetch(
        `/api/v1/games/${sessionId.value}/glass-3d?glass_number=${currentGlassNumber.value}`
      )
      if (!res.ok) return
      glass3dData.value = await res.json()
    } catch {
      // Silently fail
    } finally {
      glass3dLoading.value = false
    }
  }

  function advanceToNextUnscored() {
    for (let h = currentHole.value + 1; h <= totalHoles.value; h++) {
      if (scores.value[h] === undefined) {
        currentHole.value = h
        return
      }
    }
    // Wrap around from start
    for (let h = 1; h < currentHole.value; h++) {
      if (scores.value[h] === undefined) {
        currentHole.value = h
        return
      }
    }
    // All scored — stay on next hole
    if (currentHole.value < totalHoles.value) {
      currentHole.value++
    }
  }

  return {
    // State
    glassSetId,
    glassNumber,
    sessionId,
    playerId,
    playerName,
    courseName,
    glassCount,
    holesPerGlass,
    holes,
    courseMapSvg,
    currentHole,
    scores,
    leaderboard,
    otherPlayers,
    gameHistory,
    loading,
    connected,
    view,
    glass3dData,
    glass3dLoading,
    // Computed
    totalHoles,
    currentHoleInfo,
    currentGlassNumber,
    cumulativeScore,
    holesScored,
    // Actions
    joinGame,
    reconnect,
    submitScore,
    removeScore,
    fetchLeaderboard,
    fetchGlass3DData,
    fetchGameHistory,
    deleteGame,
    endGame,
    startScorePolling,
    stopScorePolling,
    nextHole,
    prevHole,
    advanceToNextUnscored,
    undoLastScore,
    shareLeaderboard,
    lastScoredHole,
    saveToStorage,
    loadFromStorage,
  }
})
