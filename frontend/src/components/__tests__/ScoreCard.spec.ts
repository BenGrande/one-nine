import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ScoreCard from '../ScoreCard.vue'
import { useGameStore } from '../../stores/game'

function mountComponent() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useGameStore()
  store.sessionId = 'sess-123'
  store.playerId = 'player-456'
  store.playerName = 'Mike'
  store.courseName = 'Pebble Beach'
  store.glassCount = 3
  store.holesPerGlass = 6
  store.holes = [
    { number: 1, par: 4, yards: 400, handicap: 1 },
    { number: 2, par: 3, yards: 180, handicap: 15 },
  ]
  return mount(ScoreCard, {
    global: { plugins: [pinia] },
  })
}

describe('ScoreCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders header with course name', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('Split the Tee')
    expect(wrapper.text()).toContain('Pebble Beach')
  })

  it('renders hole info', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('Hole 1')
    expect(wrapper.text()).toContain('Par 4')
    expect(wrapper.text()).toContain('400yd')
  })

  it('renders score buttons', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('-1')
    expect(wrapper.text()).toContain('E')  // 0 relative to par
    expect(wrapper.text()).toContain('+1')
    expect(wrapper.text()).toContain('+5')
  })

  it('renders penalty button', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('+8 Penalty')
  })

  it('renders hole navigator', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('Hole 1')
  })

  it('renders progress dots', () => {
    const wrapper = mountComponent()
    const dots = wrapper.findAll('footer span')
    expect(dots.length).toBe(18) // 3 glasses * 6 holes
  })

  it('renders leaderboard link', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('View Leaderboard')
  })

  it('shows player name', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('Mike')
  })

  it('shows glass number', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('Glass 1')
  })

  it('renders hole count', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('Hole 1/18')
  })
})
