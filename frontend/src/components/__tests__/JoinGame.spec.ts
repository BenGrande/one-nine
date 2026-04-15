import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import JoinGame from '../JoinGame.vue'
import { useGameStore } from '../../stores/game'

function mountComponent() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(JoinGame, {
    global: { plugins: [pinia] },
  })
}

describe('JoinGame', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders branding', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('Split the Tee')
  })

  it('renders name input', () => {
    const wrapper = mountComponent()
    const input = wrapper.find('input[type="text"]')
    expect(input.exists()).toBe(true)
    expect(input.attributes('placeholder')).toContain('Enter your name')
  })

  it('renders join button', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('Join Game')
  })

  it('shows error when trying to join with empty name', async () => {
    const wrapper = mountComponent()
    await wrapper.find('button').trigger('click')
    expect(wrapper.text()).toContain('Please enter your name')
  })

  it('calls joinGame on submit', async () => {
    const wrapper = mountComponent()
    const store = useGameStore()
    store.glassSetId = 'test-set'
    store.joinGame = vi.fn().mockResolvedValue(true)

    await wrapper.find('input').setValue('Mike')
    await wrapper.find('button').trigger('click')

    expect(store.joinGame).toHaveBeenCalledWith('test-set', 'Mike')
  })

  it('shows error when join fails', async () => {
    const wrapper = mountComponent()
    const store = useGameStore()
    store.joinGame = vi.fn().mockResolvedValue(false)

    await wrapper.find('input').setValue('Mike')
    await wrapper.find('button').trigger('click')

    expect(wrapper.text()).toContain('Could not join game')
  })

  it('shows course name when available', async () => {
    const wrapper = mountComponent()
    const store = useGameStore()
    store.courseName = 'Pebble Beach'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Pebble Beach')
  })
})
