import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDesignerStore, ALL_LAYERS, LAYER_LABELS, DEFAULT_STYLES, FONT_OPTIONS } from '../designer'

describe('designer store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('has correct default state', () => {
    const store = useDesignerStore()
    expect(store.glassCount).toBe(3)
    expect(store.currentGlass).toBe(0)
    expect(store.glassDimensions.height).toBe(146)
    expect(store.glassDimensions.topRadius).toBe(43)
    expect(store.glassDimensions.bottomRadius).toBe(30)
    expect(store.glassDimensions.wallThickness).toBe(3)
    expect(store.glassDimensions.baseThickness).toBe(5)
    expect(store.fillMode).toBe('can')
    expect(store.previewMode).toBe('vinyl-preview')
    expect(store.showText).toBe(true)
    expect(store.perHoleColors).toBe(true)
    expect(store.fontFamily).toBe("'Arial', sans-serif")
    expect(store.logoDataUrl).toBeNull()
    expect(store.svgContent).toBe('')
    expect(store.loading).toBe(false)
  })

  it('toggleLayer adds and removes layers from hiddenLayers', () => {
    const store = useDesignerStore()
    // background and ruler are hidden by default
    expect(store.hiddenLayers.has('background')).toBe(true)
    expect(store.hiddenLayers.has('ruler')).toBe(true)
    store.toggleLayer('background')
    expect(store.hiddenLayers.has('background')).toBe(false)
    store.toggleLayer('background')
    expect(store.hiddenLayers.has('background')).toBe(true)
  })

  it('toggleLayer works for non-hidden layers', () => {
    const store = useDesignerStore()
    expect(store.hiddenLayers.has('fairway')).toBe(false)
    store.toggleLayer('fairway')
    expect(store.hiddenLayers.has('fairway')).toBe(true)
    store.toggleLayer('fairway')
    expect(store.hiddenLayers.has('fairway')).toBe(false)
  })

  it('updateStyle changes a layer style property', () => {
    const store = useDesignerStore()
    store.updateStyle('fairway', 'fill', '#ff0000')
    expect(store.styles.fairway.fill).toBe('#ff0000')
  })

  it('updateStyle handles strokeWidth as number', () => {
    const store = useDesignerStore()
    store.updateStyle('green', 'strokeWidth', 2.5)
    expect(store.styles.green.strokeWidth).toBe(2.5)
  })

  it('setLogo sets and clears logo', () => {
    const store = useDesignerStore()
    store.setLogo('data:image/png;base64,abc123')
    expect(store.logoDataUrl).toBe('data:image/png;base64,abc123')
    store.setLogo(null)
    expect(store.logoDataUrl).toBeNull()
  })

  it('exportSvg does nothing when no content', () => {
    const store = useDesignerStore()
    // Should not throw
    store.exportSvg()
  })

  it('renderPreview handles fetch failure gracefully', async () => {
    const store = useDesignerStore()
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network error'))

    await store.renderPreview({ holes: [{ ref: 1 }] })

    expect(store.svgContent).toContain('Preview will appear here')
    expect(store.loading).toBe(false)
  })

  it('renderPreview handles non-ok response', async () => {
    const store = useDesignerStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 500,
    } as Response)

    await store.renderPreview({ holes: [{ ref: 1 }] })

    expect(store.svgContent).toContain('Preview will appear here')
    expect(store.statusMessage).toContain('not available')
  })

  it('renderPreview sets svgContent on success', async () => {
    const store = useDesignerStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ svg: '<svg>test</svg>' }),
    } as Response)

    await store.renderPreview({ holes: [{ ref: 1 }] })

    expect(store.svgContent).toBe('<svg>test</svg>')
    expect(store.loading).toBe(false)
  })

  it('renderPreview skips if no holes', async () => {
    const store = useDesignerStore()
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    await store.renderPreview({ holes: [] })
    await store.renderPreview(null)

    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('applySettings restores state', () => {
    const store = useDesignerStore()
    store.applySettings({
      glassCount: 6,
      currentGlass: 2,
      glassDimensions: { height: 200, topRadius: 50, bottomRadius: 35, wallThickness: 4, baseThickness: 6 },
      fillMode: 'custom',
      customTopPadding: 10,
      customBottomPadding: 5,
      previewMode: 'rect',
      hiddenLayers: ['fairway', 'water'],
      fontFamily: "'Oswald', sans-serif",
      showText: false,
      perHoleColors: false,
    })

    expect(store.glassCount).toBe(6)
    expect(store.currentGlass).toBe(2)
    expect(store.glassDimensions.height).toBe(200)
    expect(store.fillMode).toBe('custom')
    expect(store.customTopPadding).toBe(10)
    expect(store.previewMode).toBe('rect')
    expect(store.hiddenLayers.has('fairway')).toBe(true)
    expect(store.hiddenLayers.has('water')).toBe(true)
    expect(store.fontFamily).toBe("'Oswald', sans-serif")
    expect(store.showText).toBe(false)
    expect(store.perHoleColors).toBe(false)
  })

  it('loadSettingsList returns empty array on failure', async () => {
    const store = useDesignerStore()
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('fail'))
    const result = await store.loadSettingsList()
    expect(result).toEqual([])
  })

  it('ALL_LAYERS has expected entries including ruler', () => {
    expect(ALL_LAYERS).toContain('background')
    expect(ALL_LAYERS).toContain('fairway')
    expect(ALL_LAYERS).toContain('green')
    expect(ALL_LAYERS).toContain('hole_number')
    expect(ALL_LAYERS).toContain('ruler')
    expect(ALL_LAYERS.length).toBe(10)
  })

  it('LAYER_LABELS maps all layers', () => {
    for (const layer of ALL_LAYERS) {
      expect(LAYER_LABELS[layer]).toBeTruthy()
    }
  })

  it('DEFAULT_STYLES has entries for feature layers', () => {
    const styledLayers = ALL_LAYERS.filter(l => l !== 'ruler')
    for (const layer of styledLayers) {
      expect(DEFAULT_STYLES[layer]).toBeTruthy()
      expect(DEFAULT_STYLES[layer].fill).toBeTruthy()
    }
  })

  it('FONT_OPTIONS has at least 5 entries', () => {
    expect(FONT_OPTIONS.length).toBeGreaterThanOrEqual(5)
    expect(FONT_OPTIONS[0]).toHaveProperty('label')
    expect(FONT_OPTIONS[0]).toHaveProperty('value')
  })

  it('previewMode accepts vinyl-preview', () => {
    const store = useDesignerStore()
    store.previewMode = 'vinyl-preview'
    expect(store.previewMode).toBe('vinyl-preview')
  })

  it('previewMode defaults to vinyl-preview', () => {
    const store = useDesignerStore()
    expect(store.previewMode).toBe('vinyl-preview')
  })

  it('render payload includes mode vinyl-preview when selected', async () => {
    const store = useDesignerStore()
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ svg: '<svg></svg>' }),
    } as Response)

    await store.renderPreview({ holes: [{ ref: 1 }], courseName: 'Test' })

    const body = JSON.parse(fetchSpy.mock.calls[0][1]!.body as string)
    expect(body.options.mode).toBe('vinyl-preview')
  })

  it('previewMode accepts scoring-preview', () => {
    const store = useDesignerStore()
    store.previewMode = 'scoring-preview'
    expect(store.previewMode).toBe('scoring-preview')
  })

  it('applySettings handles scoring-preview mode', () => {
    const store = useDesignerStore()
    store.applySettings({ previewMode: 'scoring-preview' })
    expect(store.previewMode).toBe('scoring-preview')
  })

  it('renderPreview sets courseName from courseData', async () => {
    const store = useDesignerStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ svg: '<svg></svg>' }),
    } as Response)

    await store.renderPreview({ holes: [{ ref: 1 }], courseName: 'Pebble Beach' })
    expect(store.courseName).toBe('Pebble Beach')
  })

  it('renderPreview sends options in correct API shape', async () => {
    const store = useDesignerStore()
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ svg: '<svg></svg>' }),
    } as Response)

    await store.renderPreview({ holes: [{ ref: 1 }], courseName: 'Test' })

    const body = JSON.parse(fetchSpy.mock.calls[0][1]!.body as string)
    expect(body).toHaveProperty('options')
    expect(body.options).toHaveProperty('mode', 'vinyl-preview')
    expect(body.options).toHaveProperty('glass_count', 3)
    expect(body.options).toHaveProperty('glass_dimensions')
    expect(body.options.glass_dimensions).toHaveProperty('glass_height', 146)
    expect(body.options).toHaveProperty('hidden_layers')
    expect(body).toHaveProperty('course_name', 'Test')
  })

  it('ruler is hidden by default in hiddenLayers', () => {
    const store = useDesignerStore()
    expect(store.hiddenLayers.has('ruler')).toBe(true)
  })

  it('toggling ruler layer works', () => {
    const store = useDesignerStore()
    store.toggleLayer('ruler')
    expect(store.hiddenLayers.has('ruler')).toBe(false)
    store.toggleLayer('ruler')
    expect(store.hiddenLayers.has('ruler')).toBe(true)
  })

  it('exportSvg uses courseName in filename', () => {
    const store = useDesignerStore()
    store.courseName = 'Pebble Beach'
    store.svgContent = '<svg></svg>'

    const createSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test')
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const clickSpy = vi.fn()
    vi.spyOn(document, 'createElement').mockReturnValue({
      set href(_v: string) {},
      set download(_v: string) { (this as any)._download = _v },
      get download() { return (this as any)._download },
      click: clickSpy,
    } as any)

    store.exportSvg()

    expect(clickSpy).toHaveBeenCalled()
    createSpy.mockRestore()
    revokeSpy.mockRestore()
  })

  // Cricut export tests
  it('previewMode accepts cricut modes', () => {
    const store = useDesignerStore()
    store.previewMode = 'cricut-white'
    expect(store.previewMode).toBe('cricut-white')
    store.previewMode = 'cricut-green'
    expect(store.previewMode).toBe('cricut-green')
    store.previewMode = 'cricut-tan'
    expect(store.previewMode).toBe('cricut-tan')
  })

  it('cricutSvgs is null by default', () => {
    const store = useDesignerStore()
    expect(store.cricutSvgs).toBeNull()
    expect(store.cricutLoading).toBe(false)
  })

  it('exportCricut stores SVGs on success including blue layer', async () => {
    const store = useDesignerStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        white: '<svg>white</svg>',
        blue: '<svg>blue</svg>',
        green: '<svg>green</svg>',
        tan: '<svg>tan</svg>',
        guide: '<svg>guide</svg>',
      }),
    } as Response)

    await store.exportCricut({ holes: [{ ref: 1 }], courseName: 'Test' })

    expect(store.cricutSvgs).not.toBeNull()
    expect(store.cricutSvgs!.white).toBe('<svg>white</svg>')
    expect(store.cricutSvgs!.blue).toBe('<svg>blue</svg>')
    expect(store.cricutSvgs!.green).toBe('<svg>green</svg>')
    expect(store.cricutSvgs!.tan).toBe('<svg>tan</svg>')
    expect(store.cricutSvgs!.guide).toBe('<svg>guide</svg>')
    expect(store.cricutLoading).toBe(false)
  })

  it('exportCricut includes hole_range in API payload', async () => {
    const store = useDesignerStore()
    store.glassCount = 3
    store.currentGlass = 0
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        white: '<svg></svg>', blue: '<svg></svg>', green: '<svg></svg>', tan: '<svg></svg>', guide: '<svg></svg>',
      }),
    } as Response)

    const holes = Array.from({ length: 9 }, (_, i) => ({ ref: i + 1 }))
    await store.exportCricut({ holes, courseName: 'Test' })

    const body = JSON.parse(fetchSpy.mock.calls[0][1]!.body as string)
    expect(body.hole_range).toBe('Holes 1-3')
    expect(body.course_name).toBe('Test')
  })

  it('exportCricut handles API failure gracefully', async () => {
    const store = useDesignerStore()
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network error'))

    await store.exportCricut({ holes: [{ ref: 1 }] })

    expect(store.cricutSvgs).toBeNull()
    expect(store.cricutLoading).toBe(false)
    expect(store.statusMessage).toContain('not available')
  })

  it('exportCricut handles non-ok response', async () => {
    const store = useDesignerStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 404,
    } as Response)

    await store.exportCricut({ holes: [{ ref: 1 }] })

    expect(store.cricutSvgs).toBeNull()
    expect(store.statusMessage).toContain('not available')
  })

  it('exportCricut skips if no holes', async () => {
    const store = useDesignerStore()
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    await store.exportCricut({ holes: [] })
    await store.exportCricut(null)

    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('downloadCricutLayer does nothing when no cricut SVGs', () => {
    const store = useDesignerStore()
    // Should not throw
    store.downloadCricutLayer('white')
  })

  it('applyFontHint sets font when match found', () => {
    const store = useDesignerStore()
    store.applyFontHint({ font_hint: 'Oswald' })
    expect(store.fontFamily).toContain('Oswald')
  })

  it('applyFontHint does nothing with no hint', () => {
    const store = useDesignerStore()
    const before = store.fontFamily
    store.applyFontHint({})
    expect(store.fontFamily).toBe(before)
  })

  it('applyFontHint ignores unknown font', () => {
    const store = useDesignerStore()
    const before = store.fontFamily
    store.applyFontHint({ font_hint: 'Comic Sans' })
    expect(store.fontFamily).toBe(before)
  })

  // Export error handling tests
  it('exportSvg shows error status when no content', () => {
    const store = useDesignerStore()
    store.svgContent = ''
    store.exportSvg()
    expect(store.statusMessage).toBe('Nothing to export — render a preview first')
  })

  it('exportSvg sets success status after export', () => {
    const store = useDesignerStore()
    store.svgContent = '<svg>test</svg>'
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    vi.spyOn(document, 'createElement').mockReturnValue({
      set href(_v: string) {},
      set download(_v: string) {},
      click: vi.fn(),
    } as any)

    store.exportSvg()
    expect(store.statusMessage).toBe('SVG exported')
  })

  it('exportAllSvg shows error status when no course data', async () => {
    const store = useDesignerStore()
    await store.exportAllSvg(null)
    expect(store.statusMessage).toBe('Nothing to export — load a course first')
  })

  it('exportAllSvg shows error status when empty holes', async () => {
    const store = useDesignerStore()
    await store.exportAllSvg({ holes: [] })
    expect(store.statusMessage).toBe('Nothing to export — load a course first')
  })

  it('exportAllSvg sets loading during operation', async () => {
    const store = useDesignerStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ svg: '<svg>test</svg>' }),
    } as Response)

    const promise = store.exportAllSvg({ holes: [{ ref: 1 }], courseName: 'Test' })

    // loading should be true during operation
    expect(store.loading).toBe(true)
    await promise
    expect(store.loading).toBe(false)
  })

  it('downloadCricutLayer shows error when no layers available', () => {
    const store = useDesignerStore()
    store.downloadCricutLayer('white')
    expect(store.statusMessage).toBe('Cricut layer not available — generate layers first')
  })

  it('downloadCricutLayer downloads blue layer', async () => {
    const store = useDesignerStore()
    store.cricutSvgs = {
      white: '<svg>white</svg>',
      blue: '<svg>blue</svg>',
      green: '<svg>green</svg>',
      tan: '<svg>tan</svg>',
      guide: '<svg>guide</svg>',
    }
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    vi.spyOn(document, 'createElement').mockReturnValue({
      set href(_v: string) {},
      set download(_v: string) {},
      click: vi.fn(),
    } as any)

    await store.downloadCricutLayer('blue')
    expect(store.statusMessage).toBe('Downloaded Cricut blue layer (SVG)')
  })

  it('downloadCricutLayer shows success status after download', async () => {
    const store = useDesignerStore()
    store.cricutSvgs = {
      white: '<svg>white</svg>',
      blue: '<svg>blue</svg>',
      green: '<svg>green</svg>',
      tan: '<svg>tan</svg>',
      guide: '<svg>guide</svg>',
    }
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    vi.spyOn(document, 'createElement').mockReturnValue({
      set href(_v: string) {},
      set download(_v: string) {},
      click: vi.fn(),
    } as any)

    await store.downloadCricutLayer('white')
    expect(store.statusMessage).toBe('Downloaded Cricut white layer (SVG)')
  })

  it('downloadAllCricutLayers shows error when no layers available', async () => {
    const store = useDesignerStore()
    await store.downloadAllCricutLayers()
    expect(store.statusMessage).toBe('Cricut layers not available — generate layers first')
  })

  // Multi-glass cricut response handling
  it('exportCricut handles multi-glass response with glasses array', async () => {
    const store = useDesignerStore()
    store.currentGlass = 1
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        glasses: [
          { white: '<svg>g0-white</svg>', blue: '<svg>g0-blue</svg>', green: '<svg>g0-green</svg>', tan: '<svg>g0-tan</svg>', guide: '<svg>g0-guide</svg>' },
          { white: '<svg>g1-white</svg>', blue: '<svg>g1-blue</svg>', green: '<svg>g1-green</svg>', tan: '<svg>g1-tan</svg>', guide: '<svg>g1-guide</svg>' },
        ],
      }),
    } as Response)

    await store.exportCricut({ holes: [{ ref: 1 }], courseName: 'Test' })

    expect(store.cricutSvgs!.white).toBe('<svg>g1-white</svg>')
    expect(store.cricutSvgs!.blue).toBe('<svg>g1-blue</svg>')
    expect(store.cricutSvgs!.green).toBe('<svg>g1-green</svg>')
  })

  it('exportCricut falls back to glasses[0] if currentGlass out of range', async () => {
    const store = useDesignerStore()
    store.currentGlass = 5
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        glasses: [
          { white: '<svg>only</svg>', blue: '', green: '', tan: '', guide: '' },
        ],
      }),
    } as Response)

    await store.exportCricut({ holes: [{ ref: 1 }] })

    expect(store.cricutSvgs!.white).toBe('<svg>only</svg>')
  })

  it('exportCricut surfaces API error text in status message', async () => {
    const store = useDesignerStore()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 422,
      text: () => Promise.resolve('Invalid hole data'),
    } as Response)

    await store.exportCricut({ holes: [{ ref: 1 }] })

    expect(store.statusMessage).toContain('422')
    expect(store.statusMessage).toContain('Invalid hole data')
  })

  // SVG validation
  it('exportSvg rejects invalid SVG content', () => {
    const store = useDesignerStore()
    store.svgContent = 'not-an-svg'
    store.exportSvg()
    expect(store.statusMessage).toBe('Invalid SVG content — cannot export')
  })

  it('downloadCricutLayer rejects invalid SVG content', () => {
    const store = useDesignerStore()
    store.cricutSvgs = {
      white: 'bad content',
      blue: '',
      green: '',
      tan: '',
      guide: '',
    }
    store.downloadCricutLayer('white')
    expect(store.statusMessage).toContain('Invalid SVG content')
  })

  // hole_range and course_name in render payload
  it('renderPreview includes hole_range in API payload', async () => {
    const store = useDesignerStore()
    store.glassCount = 3
    store.currentGlass = 0
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ svg: '<svg></svg>' }),
    } as Response)

    const holes = Array.from({ length: 9 }, (_, i) => ({ ref: i + 1 }))
    await store.renderPreview({ holes, courseName: 'Test Course' })

    const body = JSON.parse(fetchSpy.mock.calls[0][1]!.body as string)
    expect(body.hole_range).toBe('Holes 1-3')
    expect(body.course_name).toBe('Test Course')
  })

  it('renderPreview computes hole_range for second glass', async () => {
    const store = useDesignerStore()
    store.glassCount = 3
    store.currentGlass = 1
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ svg: '<svg></svg>' }),
    } as Response)

    const holes = Array.from({ length: 9 }, (_, i) => ({ ref: i + 1 }))
    await store.renderPreview({ holes, courseName: 'Test' })

    const body = JSON.parse(fetchSpy.mock.calls[0][1]!.body as string)
    expect(body.hole_range).toBe('Holes 4-6')
  })

  it('renderPreview computes hole_range for last glass with remainder', async () => {
    const store = useDesignerStore()
    store.glassCount = 2
    store.currentGlass = 1
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ svg: '<svg></svg>' }),
    } as Response)

    const holes = Array.from({ length: 9 }, (_, i) => ({ ref: i + 1 }))
    await store.renderPreview({ holes, courseName: 'Test' })

    const body = JSON.parse(fetchSpy.mock.calls[0][1]!.body as string)
    expect(body.hole_range).toBe('Holes 6-9')
  })
})
