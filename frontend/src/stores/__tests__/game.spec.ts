import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useGameStore } from '../game'

describe('game store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    // Clear localStorage items we use
    try { localStorage.clear() } catch { /* happy-dom may not support clear */ }
  })

  it('has correct default state', () => {
    const store = useGameStore()
    expect(store.glassSetId).toBe('')
    expect(store.sessionId).toBeNull()
    expect(store.playerId).toBeNull()
    expect(store.playerName).toBe('')
    expect(store.courseName).toBe('')
    expect(store.glassCount).toBe(3)
    expect(store.holesPerGlass).toBe(6)
    expect(store.currentHole).toBe(1)
    expect(store.scores).toEqual({})
    expect(store.leaderboard).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.connected).toBe(false)
    expect(store.view).toBe('join')
  })

  it('totalHoles computes from glassCount * holesPerGlass', () => {
    const store = useGameStore()
    expect(store.totalHoles).toBe(18)
    store.glassCount = 2
    store.holesPerGlass = 9
    expect(store.totalHoles).toBe(18)
    store.glassCount = 6
    store.holesPerGlass = 3
    expect(store.totalHoles).toBe(18)
  })

  it('currentGlassNumber computes correctly', () => {
    const store = useGameStore()
    store.holesPerGlass = 6
    store.currentHole = 1
    expect(store.currentGlassNumber).toBe(1)
    store.currentHole = 6
    expect(store.currentGlassNumber).toBe(1)
    store.currentHole = 7
    expect(store.currentGlassNumber).toBe(2)
    store.currentHole = 18
    expect(store.currentGlassNumber).toBe(3)
  })

  it('cumulativeScore computes relative to par', () => {
    const store = useGameStore()
    store.holes = [
      { number: 1, par: 4, yards: 400, handicap: 1 },
      { number: 2, par: 3, yards: 200, handicap: 2 },
      { number: 3, par: 5, yards: 500, handicap: 3 },
    ]
    store.scores = { 1: 5, 2: 3, 3: 4 }
    // (5-4) + (3-3) + (4-5) = 1 + 0 + (-1) = 0
    expect(store.cumulativeScore).toBe(0)
  })

  it('holesScored counts scored holes', () => {
    const store = useGameStore()
    expect(store.holesScored).toBe(0)
    store.scores = { 1: 4, 5: 3 }
    expect(store.holesScored).toBe(2)
  })

  it('nextHole increments within bounds', () => {
    const store = useGameStore()
    store.glassCount = 3
    store.holesPerGlass = 6
    store.currentHole = 1
    store.nextHole()
    expect(store.currentHole).toBe(2)
  })

  it('nextHole does not exceed totalHoles', () => {
    const store = useGameStore()
    store.currentHole = 18
    store.nextHole()
    expect(store.currentHole).toBe(18)
  })

  it('prevHole decrements within bounds', () => {
    const store = useGameStore()
    store.currentHole = 5
    store.prevHole()
    expect(store.currentHole).toBe(4)
  })

  it('prevHole does not go below 1', () => {
    const store = useGameStore()
    store.currentHole = 1
    store.prevHole()
    expect(store.currentHole).toBe(1)
  })

  it('advanceToNextUnscored finds next unscored hole', () => {
    const store = useGameStore()
    store.glassCount = 3
    store.holesPerGlass = 6
    store.currentHole = 3
    store.scores = { 1: 4, 2: 3, 3: 5, 4: 4 }
    store.advanceToNextUnscored()
    expect(store.currentHole).toBe(5) // first unscored after 3
  })

  it('advanceToNextUnscored wraps around', () => {
    const store = useGameStore()
    store.glassCount = 1
    store.holesPerGlass = 3
    store.currentHole = 3
    store.scores = { 2: 4, 3: 5 }
    store.advanceToNextUnscored()
    expect(store.currentHole).toBe(1) // wraps to 1
  })

  it('joinGame calls API and sets state on success', async () => {
    const store = useGameStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        session_id: 'sess-123',
        player_id: 'player-456',
        course_name: 'Pebble Beach',
        glass_count: 3,
        holes_per_glass: 6,
        holes: [{ number: 1, par: 4, yards: 400, handicap: 1 }],
        scores: [],
      }),
    } as Response)

    const ok = await store.joinGame('set-abc', 'Mike')

    expect(ok).toBe(true)
    expect(store.sessionId).toBe('sess-123')
    expect(store.playerId).toBe('player-456')
    expect(store.courseName).toBe('Pebble Beach')
    expect(store.connected).toBe(true)
    expect(store.view).toBe('scorecard')
    expect(store.loading).toBe(false)
  })

  it('joinGame returns false on API failure', async () => {
    const store = useGameStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 500,
    } as Response)

    const ok = await store.joinGame('set-abc', 'Mike')
    expect(ok).toBe(false)
    expect(store.connected).toBe(false)
  })

  it('joinGame returns false on network error', async () => {
    const store = useGameStore()
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network error'))

    const ok = await store.joinGame('set-abc', 'Mike')
    expect(ok).toBe(false)
  })

  it('submitScore updates scores optimistically', async () => {
    const store = useGameStore()
    store.sessionId = 'sess-123'
    store.playerId = 'player-456'
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true } as Response)

    await store.submitScore(5, 4)
    expect(store.scores[5]).toBe(4)
  })

  it('submitScore calls API with correct payload', async () => {
    const store = useGameStore()
    store.sessionId = 'sess-123'
    store.playerId = 'player-456'
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true } as Response)

    await store.submitScore(7, 5)

    const body = JSON.parse(fetchSpy.mock.calls[0][1]!.body as string)
    expect(body.hole_number).toBe(7)
    expect(body.score).toBe(5)
    expect(body.player_id).toBe('player-456')
  })

  it('submitScore returns false when no session', async () => {
    const store = useGameStore()
    const result = await store.submitScore(1, 4)
    expect(result).toBe(false)
  })

  it('fetchLeaderboard stores results', async () => {
    const store = useGameStore()
    store.sessionId = 'sess-123'
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        players: [
          { player_id: 'p1', player_name: 'Mike', total_score: 70, holes_played: 18, score_to_par: -2 },
        ],
      }),
    } as Response)

    await store.fetchLeaderboard()
    expect(store.leaderboard.length).toBe(1)
    expect(store.leaderboard[0].player_name).toBe('Mike')
  })

  it('fetchLeaderboard silently fails on error', async () => {
    const store = useGameStore()
    store.sessionId = 'sess-123'
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('fail'))

    await store.fetchLeaderboard()
    expect(store.leaderboard).toEqual([])
  })

  it('saveToStorage and loadFromStorage round-trip', () => {
    const storage: Record<string, string> = {}
    const mockLS = {
      getItem: vi.fn((k: string) => storage[k] ?? null),
      setItem: vi.fn((k: string, v: string) => { storage[k] = v }),
      removeItem: vi.fn((k: string) => { delete storage[k] }),
    }
    vi.stubGlobal('localStorage', mockLS)

    const store = useGameStore()
    store.glassSetId = 'set-abc'
    store.sessionId = 'sess-123'
    store.playerId = 'player-456'
    store.playerName = 'Mike'

    store.saveToStorage()
    expect(mockLS.setItem).toHaveBeenCalled()

    const data = store.loadFromStorage()
    expect(data).not.toBeNull()
    expect(data!.sessionId).toBe('sess-123')
    expect(data!.playerId).toBe('player-456')
    expect(data!.playerName).toBe('Mike')

    vi.unstubAllGlobals()
  })

  it('loadFromStorage returns null when nothing stored', () => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })

    const store = useGameStore()
    store.glassSetId = 'set-abc'
    expect(store.loadFromStorage()).toBeNull()

    vi.unstubAllGlobals()
  })

  it('reconnect succeeds with valid stored session', async () => {
    const sessionData = JSON.stringify({
      sessionId: 'sess-123',
      playerId: 'player-456',
      playerName: 'Mike',
    })
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => sessionData),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })

    const store = useGameStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        course_name: 'Pebble Beach',
        glass_count: 3,
        holes_per_glass: 6,
        holes: [],
        scores: [],
      }),
    } as Response)

    const ok = await store.reconnect('set-abc')
    expect(ok).toBe(true)
    expect(store.sessionId).toBe('sess-123')
    expect(store.connected).toBe(true)
    expect(store.view).toBe('scorecard')

    vi.unstubAllGlobals()
  })

  it('reconnect returns false with no stored session', async () => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })

    const store = useGameStore()
    const ok = await store.reconnect('set-xyz')
    expect(ok).toBe(false)

    vi.unstubAllGlobals()
  })

  it('reconnect returns false if API rejects session', async () => {
    const sessionData = JSON.stringify({
      sessionId: 'sess-old',
      playerId: 'p-old',
      playerName: 'Test',
    })
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => sessionData),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })

    const store = useGameStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 404,
    } as Response)

    const ok = await store.reconnect('set-abc')
    expect(ok).toBe(false)

    vi.unstubAllGlobals()
  })

  it('currentHoleInfo returns correct hole data', () => {
    const store = useGameStore()
    store.holes = [
      { number: 1, par: 4, yards: 400, handicap: 1 },
      { number: 2, par: 3, yards: 180, handicap: 15 },
    ]
    store.currentHole = 2
    expect(store.currentHoleInfo.par).toBe(3)
    expect(store.currentHoleInfo.yards).toBe(180)
  })

  it('currentHoleInfo returns defaults for unknown hole', () => {
    const store = useGameStore()
    store.holes = []
    store.currentHole = 99
    expect(store.currentHoleInfo.par).toBe(4)
    expect(store.currentHoleInfo.number).toBe(99)
  })

  it('undoLastScore reverts the last score', async () => {
    const store = useGameStore()
    store.sessionId = 'sess-123'
    store.playerId = 'player-456'
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true } as Response)

    store.scores = { 1: 4 }
    await store.submitScore(2, 5)
    expect(store.scores[2]).toBe(5)
    expect(store.lastScoredHole).not.toBeNull()

    store.undoLastScore()
    expect(store.scores[2]).toBeUndefined()
    expect(store.currentHole).toBe(2)
    expect(store.lastScoredHole).toBeNull()
  })

  it('undoLastScore does nothing when no last score', () => {
    const store = useGameStore()
    store.undoLastScore()
    expect(store.lastScoredHole).toBeNull()
  })

  it('shareLeaderboard returns formatted text', () => {
    const store = useGameStore()
    store.courseName = 'Pebble Beach'
    store.leaderboard = [
      { player_id: 'p1', player_name: 'Mike', total_score: 70, holes_played: 18, score_to_par: -2 },
      { player_id: 'p2', player_name: 'Sarah', total_score: 75, holes_played: 18, score_to_par: 3 },
    ]

    const text = store.shareLeaderboard()
    expect(text).toContain('Split the Tee')
    expect(text).toContain('Pebble Beach')
    expect(text).toContain('Mike')
    expect(text).toContain('-2')
    expect(text).toContain('Sarah')
    expect(text).toContain('+3')
  })

  it('shareLeaderboard returns empty string when no entries', () => {
    const store = useGameStore()
    expect(store.shareLeaderboard()).toBe('')
  })
})
