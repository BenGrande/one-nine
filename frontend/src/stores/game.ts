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

export interface LocalPlayer {
  playerId: string
  playerName: string
  scores: Record<number, number>
}

export const useGameStore = defineStore('game', () => {
  const glassSetId = ref('')
  const glassNumber = ref(1)
  const sessionId = ref<string | null>(null)
  const courseName = ref('')
  const glassCount = ref(3)
  const holesPerGlass = ref(6)
  const holes = ref<{ number: number; par: number; yards: number; handicap: number }[]>([])
  const courseMapSvg = ref('')
  const currentHole = ref(1)
  const leaderboard = ref<LeaderboardEntry[]>([])
  const otherPlayers = ref<LeaderboardEntry[]>([])
  const gameHistory = ref<GameHistoryEntry[]>([])
  const loading = ref(false)
  const connected = ref(false)
  const view = ref<'join' | 'choice' | 'scorecard' | 'leaderboard' | 'history'>('join')
  const glass3dData = ref<Glass3DData | null>(null)
  const glass3dLoading = ref(false)

  // Multi-player support
  const localPlayers = ref<LocalPlayer[]>([])
  const activePlayerIndex = ref(0)

  // Active session info for choice screen
  const activeSessionInfo = ref<{
    sessionId: string
    courseName: string
    createdAt: string
    playerCount: number
  } | null>(null)

  // Computed proxies — delegate to the active local player
  const playerId = computed({
    get: () => localPlayers.value[activePlayerIndex.value]?.playerId ?? null,
    set: (v: string | null) => {
      if (localPlayers.value[activePlayerIndex.value] && v) {
        localPlayers.value[activePlayerIndex.value].playerId = v
      }
    },
  })

  const playerName = computed({
    get: () => localPlayers.value[activePlayerIndex.value]?.playerName ?? '',
    set: (v: string) => {
      if (localPlayers.value[activePlayerIndex.value]) {
        localPlayers.value[activePlayerIndex.value].playerName = v
      }
    },
  })

  const scores = computed({
    get: () => localPlayers.value[activePlayerIndex.value]?.scores ?? {},
    set: (v: Record<number, number>) => {
      if (localPlayers.value[activePlayerIndex.value]) {
        localPlayers.value[activePlayerIndex.value].scores = v
      }
    },
  })

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
    if (!sessionId.value || localPlayers.value.length === 0) return
    try {
      localStorage.setItem(storageKey(), JSON.stringify({
        sessionId: sessionId.value,
        players: localPlayers.value.map(p => ({
          playerId: p.playerId,
          playerName: p.playerName,
        })),
      }))
    } catch { /* localStorage may be unavailable */ }
  }

  function loadFromStorage(): { sessionId: string; players: { playerId: string; playerName: string }[] } | null {
    try {
      const data = localStorage.getItem(storageKey())
      if (!data) return null
      const parsed = JSON.parse(data)
      // Migrate old format: { sessionId, playerId, playerName }
      if (parsed.playerId && !parsed.players) {
        return {
          sessionId: parsed.sessionId,
          players: [{ playerId: parsed.playerId, playerName: parsed.playerName }],
        }
      }
      return parsed
    } catch {
      return null
    }
  }

  async function joinGame(setId: string, name: string) {
    glassSetId.value = setId
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
      courseName.value = data.course_name || ''
      glassCount.value = data.glass_count || 3
      holesPerGlass.value = data.holes_per_glass || 6
      holes.value = data.holes || []
      courseMapSvg.value = data.course_map_svg || ''

      const playerScores: Record<number, number> = {}
      if (data.scores) {
        for (const s of data.scores) {
          playerScores[s.hole_number] = s.score
        }
      }

      // Add as first local player
      localPlayers.value = [{
        playerId: data.player_id,
        playerName: data.player_name,
        scores: playerScores,
      }]
      activePlayerIndex.value = 0

      connected.value = true
      saveToStorage()

      return true
    } catch {
      return false
    } finally {
      loading.value = false
    }
  }

  async function addPlayer(name: string) {
    if (!sessionId.value) return false
    loading.value = true

    try {
      const res = await fetch('/api/v1/games/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ glass_set_id: glassSetId.value, player_name: name }),
      })

      if (!res.ok) {
        loading.value = false
        return false
      }

      const data = await res.json()
      localPlayers.value.push({
        playerId: data.player_id,
        playerName: data.player_name,
        scores: {},
      })
      saveToStorage()
      return true
    } catch {
      return false
    } finally {
      loading.value = false
    }
  }

  function switchPlayer(index: number) {
    if (index >= 0 && index < localPlayers.value.length) {
      activePlayerIndex.value = index
    }
  }

  async function reconnect(setId: string) {
    glassSetId.value = setId
    const stored = loadFromStorage()
    if (!stored) return false

    loading.value = true
    try {
      // Reconnect with the first stored player to get session info
      const firstPlayer = stored.players[0]
      const res = await fetch(
        `/api/v1/games/${stored.sessionId}/status?player_id=${firstPlayer.playerId}`
      )
      if (!res.ok) {
        localStorage.removeItem(storageKey())
        return false
      }

      const data = await res.json()

      // Check session age — if older than 2 hours, show choice screen
      if (data.created_at) {
        const created = new Date(data.created_at).getTime()
        const twoHoursMs = 2 * 60 * 60 * 1000
        if (Date.now() - created > twoHoursMs) {
          localStorage.removeItem(storageKey())
          connected.value = false
          courseName.value = data.course_name || ''
          const hasActive = await checkActiveSession(setId)
          view.value = hasActive ? 'choice' : 'join'
          return false
        }
      }

      sessionId.value = stored.sessionId
      courseName.value = data.course_name || ''
      glassCount.value = data.glass_count || 3
      holesPerGlass.value = data.holes_per_glass || 6
      holes.value = data.holes || []
      courseMapSvg.value = data.course_map_svg || ''

      // Rebuild local players from stored data
      const firstPlayerScores: Record<number, number> = {}
      if (data.scores) {
        for (const s of data.scores) {
          firstPlayerScores[s.hole_number] = s.score
        }
      }

      localPlayers.value = [{
        playerId: firstPlayer.playerId,
        playerName: firstPlayer.playerName,
        scores: firstPlayerScores,
      }]

      // Fetch scores for additional stored players
      for (let i = 1; i < stored.players.length; i++) {
        const sp = stored.players[i]
        try {
          const pRes = await fetch(
            `/api/v1/games/${stored.sessionId}/scores/${sp.playerId}`
          )
          const pScores: Record<number, number> = {}
          if (pRes.ok) {
            const pData = await pRes.json()
            for (const s of (pData.scores || [])) {
              pScores[s.hole_number] = s.score
            }
          }
          localPlayers.value.push({
            playerId: sp.playerId,
            playerName: sp.playerName,
            scores: pScores,
          })
        } catch {
          // If we can't fetch scores for a stored player, still add them
          localPlayers.value.push({
            playerId: sp.playerId,
            playerName: sp.playerName,
            scores: {},
          })
        }
      }

      activePlayerIndex.value = 0
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

  async function submitScore(holeNumber: number, score: number, playerIndex?: number) {
    if (!sessionId.value) return false
    const idx = playerIndex ?? activePlayerIndex.value
    const player = localPlayers.value[idx]
    if (!player) return false

    const oldScore = player.scores[holeNumber]
    lastScoredHole.value = { hole: holeNumber, score: oldScore, playerIndex: idx }
    player.scores = { ...player.scores, [holeNumber]: score }

    try {
      const res = await fetch(`/api/v1/games/${sessionId.value}/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_id: player.playerId,
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

  async function removeScore(holeNumber: number, playerIndex?: number) {
    if (!sessionId.value) return false
    const idx = playerIndex ?? activePlayerIndex.value
    const player = localPlayers.value[idx]
    if (!player) return false

    const oldScore = player.scores[holeNumber]
    const updated = { ...player.scores }
    delete updated[holeNumber]
    player.scores = updated

    try {
      const res = await fetch(
        `/api/v1/games/${sessionId.value}/score?player_id=${player.playerId}&hole_number=${holeNumber}`,
        { method: 'DELETE' },
      )
      if (!res.ok) {
        if (oldScore !== undefined) player.scores = { ...player.scores, [holeNumber]: oldScore }
        return false
      }
      return true
    } catch {
      if (oldScore !== undefined) player.scores = { ...player.scores, [holeNumber]: oldScore }
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

      // Sync local player scores from leaderboard
      const localIds = new Set(localPlayers.value.map(p => p.playerId))
      for (const entry of entries) {
        if (localIds.has(entry.player_id)) {
          const lp = localPlayers.value.find(p => p.playerId === entry.player_id)
          if (lp && entry.scores_by_hole) {
            const synced: Record<number, number> = {}
            for (const s of entry.scores_by_hole) {
              synced[s.hole_number] = s.score
            }
            lp.scores = synced
          }
        }
      }

      // Extract other players' scores (not any local player)
      otherPlayers.value = entries.filter(e => !localIds.has(e.player_id))
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

  async function resumeGame(targetSessionId: string): Promise<boolean> {
    loading.value = true
    try {
      const res = await fetch(`/api/v1/games/${targetSessionId}`)
      if (!res.ok) return false
      const session = await res.json()

      const sessionPlayers: { player_id: string; player_name: string }[] = session.players || []
      if (sessionPlayers.length === 0) return false

      sessionId.value = session.id
      glassSetId.value = session.glass_set_id || glassSetId.value
      courseName.value = session.course_name || ''
      glassCount.value = session.glass_count || 3
      holesPerGlass.value = session.holes_per_glass || 6
      holes.value = session.holes || []
      courseMapSvg.value = session.course_map_svg || ''

      const rebuilt: LocalPlayer[] = []
      for (const p of sessionPlayers) {
        const scoresByHole: Record<number, number> = {}
        try {
          const scoreRes = await fetch(`/api/v1/games/${targetSessionId}/scores/${p.player_id}`)
          if (scoreRes.ok) {
            const scoreData = await scoreRes.json()
            for (const s of (scoreData.scores || [])) {
              scoresByHole[s.hole_number] = s.score
            }
          }
        } catch { /* continue with empty scores */ }
        rebuilt.push({
          playerId: p.player_id,
          playerName: p.player_name,
          scores: scoresByHole,
        })
      }

      localPlayers.value = rebuilt
      activePlayerIndex.value = 0
      connected.value = true
      view.value = 'scorecard'
      saveToStorage()
      startScorePolling()
      return true
    } catch {
      return false
    } finally {
      loading.value = false
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
  const lastScoredHole = ref<{ hole: number; score: number | undefined; playerIndex: number } | null>(null)

  function undoLastScore() {
    if (!lastScoredHole.value) return
    const { hole, score, playerIndex } = lastScoredHole.value
    const player = localPlayers.value[playerIndex]
    if (!player) { lastScoredHole.value = null; return }
    const updated = { ...player.scores }
    if (score === undefined) {
      delete updated[hole]
    } else {
      updated[hole] = score
    }
    player.scores = updated
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

  // Choice screen — check for active session
  async function checkActiveSession(setId: string): Promise<boolean> {
    try {
      const res = await fetch(`/api/v1/games/glass-set/${setId}/active`)
      if (!res.ok) return false
      const data = await res.json()
      if (data.has_active_session) {
        activeSessionInfo.value = {
          sessionId: data.session_id,
          courseName: data.course_name,
          createdAt: data.created_at,
          playerCount: data.player_count,
        }
        courseName.value = data.course_name || courseName.value
        return true
      }
      activeSessionInfo.value = null
      return false
    } catch {
      return false
    }
  }

  async function startNewGame() {
    // End the active session if one exists
    if (activeSessionInfo.value) {
      try {
        await fetch(`/api/v1/games/${activeSessionInfo.value.sessionId}/end`, { method: 'POST' })
      } catch { /* best effort */ }
    }
    activeSessionInfo.value = null
    view.value = 'join'
  }

  async function resetAndStartNew() {
    // End current session
    await endGame()
    stopScorePolling()

    // Clear localStorage
    try { localStorage.removeItem(storageKey()) } catch {}

    // Reset state
    sessionId.value = null
    localPlayers.value = []
    activePlayerIndex.value = 0
    leaderboard.value = []
    otherPlayers.value = []
    connected.value = false
    currentHole.value = 1
    lastScoredHole.value = null
    glass3dData.value = null

    // Check for active session and show choice/join
    const hasActive = await checkActiveSession(glassSetId.value)
    view.value = hasActive ? 'choice' : 'join'
  }

  return {
    // State
    glassSetId,
    glassNumber,
    sessionId,
    courseName,
    glassCount,
    holesPerGlass,
    holes,
    courseMapSvg,
    currentHole,
    leaderboard,
    otherPlayers,
    gameHistory,
    loading,
    connected,
    view,
    glass3dData,
    glass3dLoading,
    // Multi-player
    localPlayers,
    activePlayerIndex,
    activeSessionInfo,
    // Computed proxies
    playerId,
    playerName,
    scores,
    // Computed
    totalHoles,
    currentHoleInfo,
    currentGlassNumber,
    cumulativeScore,
    holesScored,
    // Actions
    joinGame,
    addPlayer,
    switchPlayer,
    reconnect,
    resumeGame,
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
    checkActiveSession,
    startNewGame,
    resetAndStartNew,
  }
})
