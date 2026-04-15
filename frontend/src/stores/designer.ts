import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

const DEFAULT_STYLES: Record<string, { fill: string; stroke: string; strokeWidth: number; opacity: number }> = {
  background: { fill: '#1a472a', stroke: 'none', strokeWidth: 0, opacity: 1 },
  rough: { fill: '#8ab878', stroke: 'none', strokeWidth: 0, opacity: 0.5 },
  fairway: { fill: '#4a8f3f', stroke: '#3d7a34', strokeWidth: 0.3, opacity: 0.85 },
  bunker: { fill: '#e8dca0', stroke: '#d4c87a', strokeWidth: 0.3, opacity: 0.9 },
  water: { fill: '#5b9bd5', stroke: '#4a87be', strokeWidth: 0.3, opacity: 0.85 },
  tee: { fill: '#7bc96a', stroke: '#5eaa50', strokeWidth: 0.3, opacity: 0.9 },
  green: { fill: '#5cc654', stroke: '#3eaa36', strokeWidth: 0.5, opacity: 0.95 },
  hole_number: { fill: 'rgba(0,0,0,0.65)', stroke: '#ffffff', strokeWidth: 0.4, opacity: 1 },
  hole_par: { fill: 'rgba(255,255,255,0.5)', stroke: 'none', strokeWidth: 0, opacity: 1 },
}

export const ALL_LAYERS = [
  'background', 'rough', 'fairway', 'water', 'bunker', 'tee', 'green',
  'hole_number', 'hole_par', 'ruler',
]

export const LAYER_LABELS: Record<string, string> = {
  background: 'Background',
  rough: 'Rough',
  fairway: 'Fairway',
  water: 'Water',
  bunker: 'Bunker',
  tee: 'Tee Box',
  green: 'Green',
  hole_number: 'Hole Numbers',
  hole_par: 'Par Labels',
  ruler: 'Ruler',
}

export const FONT_OPTIONS = [
  { label: 'Arial', value: "'Arial', sans-serif" },
  { label: 'Oswald', value: "'Oswald', sans-serif" },
  { label: 'Bebas Neue', value: "'Bebas Neue', sans-serif" },
  { label: 'Montserrat', value: "'Montserrat', sans-serif" },
  { label: 'Playfair Display', value: "'Playfair Display', serif" },
  { label: 'Roboto Condensed', value: "'Roboto Condensed', sans-serif" },
  { label: 'Lato', value: "'Lato', sans-serif" },
  { label: 'Raleway', value: "'Raleway', sans-serif" },
  { label: 'Merriweather', value: "'Merriweather', serif" },
  { label: 'Poppins', value: "'Poppins', sans-serif" },
  { label: 'Cormorant Garamond', value: "'Cormorant Garamond', serif" },
  { label: 'Cinzel', value: "'Cinzel', serif" },
  { label: 'Fjalla One', value: "'Fjalla One', sans-serif" },
  { label: 'Anton', value: "'Anton', sans-serif" },
  { label: 'Staatliches', value: "'Staatliches', sans-serif" },
  { label: 'Righteous', value: "'Righteous', sans-serif" },
  { label: 'Archivo Black', value: "'Archivo Black', sans-serif" },
]

export { DEFAULT_STYLES }

export const useDesignerStore = defineStore('designer', () => {
  const glassCount = ref(3)
  const currentGlass = ref(0)

  const glassDimensions = reactive({
    height: 134.8,
    topRadius: 44.2,
    bottomRadius: 31.6,
    wallThickness: 3.1,
    baseThickness: 11.5,
  })

  const fillMode = ref<'full' | 'can' | 'custom'>('can')
  const customTopPadding = ref(0)
  const customBottomPadding = ref(2)

  const previewMode = ref<'vinyl-preview' | 'glass' | 'rect' | 'scoring-preview' | 'cricut-white' | 'cricut-blue' | 'cricut-green' | 'cricut-tan'>('vinyl-preview')
  const hiddenLayers = ref<Set<string>>(new Set(['background', 'ruler']))
  const styles = ref<Record<string, { fill: string; stroke: string; strokeWidth: number; opacity: number }>>(
    JSON.parse(JSON.stringify(DEFAULT_STYLES))
  )

  const fontFamily = ref("'Arial', sans-serif")
  const logoDataUrl = ref<string | null>(null)
  const showText = ref(true)
  const perHoleColors = ref(true)
  const showScoreLines = ref(false)
  const scorecardUrl = ref<string | null>(null)
  const glassSetId = ref<string | null>(null)
  const recipientName = ref('')

  const svgContent = ref('')
  const loading = ref(false)
  const statusMessage = ref('Ready')

  function toggleLayer(layer: string) {
    const s = new Set(hiddenLayers.value)
    if (s.has(layer)) {
      s.delete(layer)
    } else {
      s.add(layer)
    }
    hiddenLayers.value = s
  }

  function updateStyle(layer: string, prop: string, value: string | number) {
    const current = { ...styles.value }
    current[layer] = { ...current[layer], [prop]: value }
    styles.value = current
  }

  function setLogo(dataUrl: string | null) {
    logoDataUrl.value = dataUrl
  }

  // Track course name for export filenames
  const courseName = ref('')

  function applyFontHint(courseData: any) {
    const hint = courseData?.font_hint
    if (!hint) return
    const match = FONT_OPTIONS.find(f => f.label.toLowerCase() === hint.toLowerCase() || f.value.includes(hint))
    if (match) fontFamily.value = match.value
  }

  function openPrintTest() {
    if (!svgContent.value) return
    const d = glassDimensions
    const radiusDiff = d.topRadius - d.bottomRadius
    const slantH = Math.sqrt(d.height * d.height + radiusDiff * radiusDiff)
    const topCirc = 2 * Math.PI * d.topRadius

    // The SVG viewBox units ARE mm (1 unit = 1 mm).
    // Extract viewBox to get the actual print dimensions.
    const vbMatch = svgContent.value.match(/viewBox="([^"]+)"/)
    let vbW = 283, vbH = 176
    if (vbMatch) {
      const parts = vbMatch[1].split(/\s+/).map(Number)
      vbW = parts[2]
      vbH = parts[3]
    }

    // Print at actual size (1:1) — no scaling down to fit
    const marginMm = 0
    const scale = 1
    const printW = vbW
    const scalePercent = '100'

    // Invert SVG colors for print: white bg, black elements.
    // Use placeholders to avoid double-replacement.
    // Fix SVG width/height to use mm units so browser scales correctly
    let printSvg = svgContent.value
      .replace(/width="\d+"/, `width="${printW.toFixed(1)}mm"`)
      .replace(/height="\d+"/, `height="${(vbH * scale).toFixed(1)}mm"`)

    // Strip out all <mask> elements before color inversion, then add them back.
    // Masks use fill="white"/fill="black" for visibility which must not be inverted.
    const masks: string[] = []
    printSvg = printSvg.replace(/<mask[^>]*>.*?<\/mask>/gs, (match) => {
      masks.push(match)
      return `__MASK_${masks.length - 1}__`
    })

    // Invert colors: dark bg → white, white elements → black
    printSvg = printSvg
      .replace(/fill="#1a1a1a"/g, 'fill="__WHITEBG__"')
      .replace(/fill="#ffffff"/g, 'fill="#000000"')
      .replace(/fill="white"/g, 'fill="black"')
      .replace(/stroke="#ffffff"/g, 'stroke="#000000"')
      .replace(/stroke="white"/g, 'stroke="black"')
      .replace(/fill="__WHITEBG__"/g, 'fill="#ffffff"')
      // Darken colored fills for contrast on white paper
      .replace(/fill="#4ade80"/g, 'fill="#2d8f2d"')
      .replace(/stroke="#4ade80"/g, 'stroke="#1a6b1a"')
      .replace(/fill="#3b82f6"/g, 'fill="#2563eb"')
      .replace(/stroke="#3b82f6"/g, 'stroke="#1d4ed8"')
      .replace(/fill="#d2b48c"/g, 'fill="#a0845c"')

    // Restore masks untouched
    masks.forEach((m, i) => {
      printSvg = printSvg.replace(`__MASK_${i}__`, m)
    })

    const printWindow = window.open('', '_blank')
    if (!printWindow) return
    printWindow.document.write(`<!DOCTYPE html>
<html><head><title>Print Test — Split the Tee</title>
<style>
@page { size: landscape; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Arial, sans-serif; background: #fff; }
.info { font-size: 8pt; color: #666; margin: 0 0 2mm 0; }
.info strong { color: #333; }
.wrap-outer { width: ${printW.toFixed(1)}mm; overflow: visible; margin: 0 auto; }
.wrap-outer svg { width: ${printW.toFixed(1)}mm; display: block; }
.scale-ruler { margin: 2mm auto 0; width: 100mm; height: 4mm; border: 0.3mm solid #000; text-align: center; font-size: 7pt; line-height: 4mm; color: #333; }
@media print { .no-print { display: none !important; } }
</style></head><body>
<div class="info"><strong>${courseName.value || 'Course'}</strong> — Glass ${currentGlass.value + 1} | <strong>100% scale (actual size)</strong> | Wrap: ${topCirc.toFixed(0)}mm × ${slantH.toFixed(0)}mm | Glass: H=${d.height}mm, Top⌀=${(d.topRadius * 2).toFixed(0)}mm, Bot⌀=${(d.bottomRadius * 2).toFixed(0)}mm</div>
<div class="info" style="color:#c00;font-weight:bold;">⚠ In print dialog: set Margins to "None" and Scale to "Default" (100%). The wrap is ${vbW.toFixed(0)}mm wide — it may clip on letter paper.</div>
<div class="wrap-outer">${printSvg}</div>
<div class="scale-ruler">100mm ruler — verify print scale</div>
<div style="text-align:center;margin-top:2mm;">
<span style="font-size:7pt;color:#888;">Cut along glass outline. Top edge = lip of glass.</span><br>
<button class="no-print" onclick="window.print()" style="margin-top:3mm;padding:8px 24px;font-size:11pt;cursor:pointer;">Print</button>
</div></body></html>`)
    printWindow.document.close()
    statusMessage.value = 'Print test page opened — 1:1 scale, landscape'
  }

  function computeHoleRange(holes: any[]): string {
    const totalHoles = holes.length
    const perGlass = Math.ceil(totalHoles / glassCount.value)
    const start = currentGlass.value * perGlass
    const end = Math.min(start + perGlass, totalHoles)
    if (start >= totalHoles) return ''
    const firstHole = holes[start]?.ref ?? (start + 1)
    const lastHole = holes[end - 1]?.ref ?? end
    return `Holes ${firstHole}-${lastHole}`
  }

  async function renderPreview(courseData: any) {
    if (!courseData?.holes?.length) return
    loading.value = true
    statusMessage.value = 'Rendering...'
    if (courseData.courseName) courseName.value = courseData.courseName

    const holeRange = computeHoleRange(courseData.holes)

    try {
      // Pass lat/lng from courseData.center as fallback
      const opts = buildRenderOptions()
      if (!opts.course_lat && courseData.center) {
        opts.course_lat = courseData.center[0]
        opts.course_lng = courseData.center[1]
      }
      const res = await fetch('/api/v1/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          holes: courseData.holes,
          course_name: courseData.courseName || '',
          hole_range: holeRange,
          options: opts,
        }),
      })

      if (!res.ok) {
        statusMessage.value = 'Render API not available — showing placeholder'
        svgContent.value = buildPlaceholderSvg()
        return
      }

      const data = await res.json()
      svgContent.value = data.svg || ''
      // Capture glass_set_id from response and update URL
      if (data.glass_set_id && data.glass_set_id !== glassSetId.value) {
        glassSetId.value = data.glass_set_id
        const url = new URL(window.location.href)
        url.searchParams.set('glassSetId', data.glass_set_id)
        window.history.replaceState({}, '', url.toString())
      }
      statusMessage.value = `Glass ${currentGlass.value + 1}/${glassCount.value} — ${previewMode.value} mode`
    } catch {
      statusMessage.value = 'Render API not available — showing placeholder'
      svgContent.value = buildPlaceholderSvg()
    } finally {
      loading.value = false
    }
  }

  function buildPlaceholderSvg(): string {
    const bg = styles.value.background?.fill || '#1a472a'
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="400" height="300">
      <rect width="400" height="300" fill="${bg}" rx="8"/>
      <text x="200" y="140" text-anchor="middle" fill="rgba(255,255,255,0.4)" font-size="16" font-family="sans-serif">Preview will appear here</text>
      <text x="200" y="165" text-anchor="middle" fill="rgba(255,255,255,0.25)" font-size="12" font-family="sans-serif">Render API not yet available</text>
    </svg>`
  }

  function exportSvg() {
    if (!svgContent.value) {
      statusMessage.value = 'Nothing to export — render a preview first'
      return
    }
    if (!isValidSvg(svgContent.value)) {
      statusMessage.value = 'Invalid SVG content — cannot export'
      return
    }
    try {
      const blob = new Blob([svgContent.value], { type: 'image/svg+xml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const safeName = (courseName.value || 'course').replace(/[^a-zA-Z0-9]/g, '_')
      a.download = `SplitTheTee_${safeName}_Glass${currentGlass.value + 1}_${previewMode.value}.svg`
      a.click()
      URL.revokeObjectURL(url)
      statusMessage.value = 'SVG exported'
    } catch {
      statusMessage.value = 'Export failed — could not create SVG file'
    }
  }

  async function exportAllSvg(courseData: any) {
    if (!courseData?.holes?.length) {
      statusMessage.value = 'Nothing to export — load a course first'
      return
    }
    loading.value = true
    statusMessage.value = 'Generating ZIP of all glasses...'

    try {
      const JSZip = (await import('jszip')).default
      const zip = new JSZip()
      const safeName = (courseName.value || 'course').replace(/[^a-zA-Z0-9]/g, '_')
      const savedGlass = currentGlass.value

      for (let i = 0; i < glassCount.value; i++) {
        currentGlass.value = i
        await renderPreview(courseData)
        if (svgContent.value) {
          zip.file(`SplitTheTee_${safeName}_Glass${i + 1}_${previewMode.value}.svg`, svgContent.value)
        }
      }

      currentGlass.value = savedGlass
      await renderPreview(courseData)

      const blob = await zip.generateAsync({ type: 'blob' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `SplitTheTee_${safeName}_AllGlasses.zip`
      a.click()
      URL.revokeObjectURL(url)
      statusMessage.value = `Exported ${glassCount.value} SVGs as ZIP`
    } catch {
      statusMessage.value = 'Export failed — could not generate ZIP'
    } finally {
      loading.value = false
    }
  }

  // Cricut export state
  const cricutSvgs = ref<{ white: string; blue: string; green: string; tan: string; guide: string } | null>(null)
  const cricutLoading = ref(false)
  const consolidateLayers = ref(false)

  function buildRenderOptions() {
    // Extract course lat/lng from URL query params or route
    const urlParams = new URLSearchParams(window.location.search)
    const courseLat = urlParams.get('lat') ? parseFloat(urlParams.get('lat')!) : undefined
    const courseLng = urlParams.get('lng') ? parseFloat(urlParams.get('lng')!) : undefined

    return {
      mode: previewMode.value,
      glass_count: glassCount.value,
      current_glass: currentGlass.value,
      glass_dimensions: {
        glass_height: glassDimensions.height,
        top_radius: glassDimensions.topRadius,
        bottom_radius: glassDimensions.bottomRadius,
        wall_thickness: glassDimensions.wallThickness,
        base_thickness: glassDimensions.baseThickness,
      },
      fill_mode: fillMode.value,
      custom_top_padding: customTopPadding.value,
      custom_bottom_padding: customBottomPadding.value,
      hidden_layers: [...hiddenLayers.value],
      styles: styles.value,
      font_family: fontFamily.value,
      show_text: showText.value,
      per_hole_colors: perHoleColors.value,
      logo_data_url: logoDataUrl.value,
      show_score_lines: showScoreLines.value,
      scorecard_url: scorecardUrl.value,
      glass_set_id: glassSetId.value,
      recipient_name: recipientName.value,
      course_lat: courseLat,
      course_lng: courseLng,
      consolidate_layers: consolidateLayers.value,
    }
  }

  async function exportCricut(courseData: any) {
    if (!courseData?.holes?.length) return
    cricutLoading.value = true
    statusMessage.value = 'Generating Cricut layers...'

    const holeRange = computeHoleRange(courseData.holes)

    try {
      const res = await fetch('/api/v1/render/cricut', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          holes: courseData.holes,
          course_name: courseData.courseName || '',
          hole_range: holeRange,
          options: buildRenderOptions(),
        }),
      })

      if (!res.ok) {
        const errText = await res.text().catch(() => '')
        statusMessage.value = `Cricut export failed: ${res.status}${errText ? ' — ' + errText : ''}`
        cricutSvgs.value = null
        return
      }

      const data = await res.json()
      const layerData = data.glasses
        ? (data.glasses[currentGlass.value] || data.glasses[0])
        : data
      cricutSvgs.value = {
        white: layerData.white || '',
        blue: layerData.blue || '',
        green: layerData.green || '',
        tan: layerData.tan || '',
        guide: layerData.guide || '',
      }
      statusMessage.value = 'Cricut layers generated'
    } catch (error) {
      console.error('Cricut export failed:', error)
      statusMessage.value = 'Cricut export API not available'
      cricutSvgs.value = null
    } finally {
      cricutLoading.value = false
    }
  }

  function isValidSvg(content: string): boolean {
    const trimmed = content.trim()
    return trimmed.startsWith('<svg') || trimmed.startsWith('<?xml')
  }

  function downloadCricutLayer(layer: 'white' | 'blue' | 'green' | 'tan' | 'guide') {
    if (!cricutSvgs.value?.[layer]) {
      statusMessage.value = 'Cricut layer not available — generate layers first'
      return
    }
    if (!isValidSvg(cricutSvgs.value[layer])) {
      statusMessage.value = `Invalid SVG content for ${layer} layer — cannot download`
      return
    }
    try {
      const blob = new Blob([cricutSvgs.value[layer]], { type: 'image/svg+xml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const safeName = (courseName.value || 'course').replace(/[^a-zA-Z0-9]/g, '_')
      a.download = `SplitTheTee_${safeName}_Cricut_${layer}.svg`
      a.click()
      URL.revokeObjectURL(url)
      statusMessage.value = `Downloaded Cricut ${layer} layer`
    } catch {
      statusMessage.value = 'Download failed — could not create SVG file'
    }
  }

  async function downloadAllCricutLayers() {
    if (!cricutSvgs.value) {
      statusMessage.value = 'Cricut layers not available — generate layers first'
      return
    }

    try {
      const JSZip = (await import('jszip')).default
      const zip = new JSZip()
      const safeName = (courseName.value || 'course').replace(/[^a-zA-Z0-9]/g, '_')

      if (cricutSvgs.value.white) zip.file(`SplitTheTee_${safeName}_Cricut_white.svg`, cricutSvgs.value.white)
      if (cricutSvgs.value.blue) zip.file(`SplitTheTee_${safeName}_Cricut_blue.svg`, cricutSvgs.value.blue)
      if (cricutSvgs.value.green) zip.file(`SplitTheTee_${safeName}_Cricut_green.svg`, cricutSvgs.value.green)
      if (cricutSvgs.value.tan) zip.file(`SplitTheTee_${safeName}_Cricut_tan.svg`, cricutSvgs.value.tan)
      if (cricutSvgs.value.guide) zip.file(`SplitTheTee_${safeName}_Cricut_guide.svg`, cricutSvgs.value.guide)

      const blob = await zip.generateAsync({ type: 'blob' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `SplitTheTee_${safeName}_Cricut.zip`
      a.click()
      URL.revokeObjectURL(url)
      statusMessage.value = 'Cricut layers downloaded as ZIP'
    } catch {
      statusMessage.value = 'Download failed — could not generate ZIP'
    }
  }

  async function saveSettings(courseName: string, courseId: string | null, lat: number | null, lng: number | null) {
    const settings = {
      courseName,
      courseId,
      lat,
      lng,
      savedAt: new Date().toISOString(),
      glassCount: glassCount.value,
      currentGlass: currentGlass.value,
      glassDimensions: { ...glassDimensions },
      fillMode: fillMode.value,
      customTopPadding: customTopPadding.value,
      customBottomPadding: customBottomPadding.value,
      previewMode: previewMode.value,
      hiddenLayers: [...hiddenLayers.value],
      styles: styles.value,
      fontFamily: fontFamily.value,
      showText: showText.value,
      perHoleColors: perHoleColors.value,
      logoDataUrl: logoDataUrl.value,
    }

    try {
      const res = await fetch('/api/v1/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      const result = await res.json()
      if (result.ok) {
        statusMessage.value = `Settings saved: ${result.filename}`
      } else {
        statusMessage.value = 'Save failed: ' + (result.error || '')
      }
      return result
    } catch {
      statusMessage.value = 'Save failed — API not available'
      // Fallback: download as file
      const blob = new Blob([JSON.stringify(settings, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `SplitTheTee_${courseName.replace(/[^a-zA-Z0-9]/g, '_')}_Settings.json`
      a.click()
      URL.revokeObjectURL(url)
      return null
    }
  }

  async function loadSettingsList(): Promise<any[]> {
    try {
      const res = await fetch('/api/v1/settings')
      if (!res.ok) return []
      return await res.json()
    } catch {
      return []
    }
  }

  async function loadSettings(id: string) {
    try {
      const res = await fetch(`/api/v1/settings/${encodeURIComponent(id)}`)
      if (!res.ok) {
        statusMessage.value = 'Failed to load settings'
        return null
      }
      const s = await res.json()
      applySettings(s)
      return s
    } catch {
      statusMessage.value = 'Load failed — API not available'
      return null
    }
  }

  function applySettings(s: any) {
    if (s.glassCount) glassCount.value = s.glassCount
    if (s.currentGlass !== undefined) currentGlass.value = s.currentGlass
    if (s.glassDimensions) Object.assign(glassDimensions, s.glassDimensions)
    if (s.fillMode) fillMode.value = s.fillMode
    if (s.customTopPadding !== undefined) customTopPadding.value = s.customTopPadding
    if (s.customBottomPadding !== undefined) customBottomPadding.value = s.customBottomPadding
    if (s.previewMode) previewMode.value = s.previewMode
    if (s.hiddenLayers) hiddenLayers.value = new Set(s.hiddenLayers)
    if (s.styles) styles.value = s.styles
    if (s.fontFamily) fontFamily.value = s.fontFamily
    if (s.showText !== undefined) showText.value = s.showText
    if (s.perHoleColors !== undefined) perHoleColors.value = s.perHoleColors
    if (s.logoDataUrl !== undefined) logoDataUrl.value = s.logoDataUrl
  }

  return {
    // State
    glassCount,
    currentGlass,
    glassDimensions,
    fillMode,
    customTopPadding,
    customBottomPadding,
    previewMode,
    hiddenLayers,
    styles,
    fontFamily,
    logoDataUrl,
    showText,
    perHoleColors,
    showScoreLines,
    scorecardUrl,
    glassSetId,
    recipientName,
    courseName,
    svgContent,
    loading,
    statusMessage,
    cricutSvgs,
    cricutLoading,
    consolidateLayers,
    // Actions
    toggleLayer,
    updateStyle,
    setLogo,
    renderPreview,
    exportSvg,
    exportAllSvg,
    exportCricut,
    downloadCricutLayer,
    downloadAllCricutLayers,
    applyFontHint,
    openPrintTest,
    saveSettings,
    loadSettingsList,
    loadSettings,
    applySettings,
  }
})
