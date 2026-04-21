import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { Glass3DData } from '../types/glass3d'
import { computeBeerHeight } from './useGlassBeerLevel'

const SCALE = 0.01 // mm to scene units (1 unit = 100mm)

interface GlassScene {
  updateBeerLevel: (
    scores: Record<number, number>,
    holes: { number: number; par: number }[],
    glassNumber: number,
  ) => void
  dispose: () => void
}

export interface GlassSceneOptions {
  /** Hex color for the canvas background. Defaults to 0x111111. */
  backgroundColor?: number
  /** Lock vertical (polar) rotation so the glass only spins horizontally. */
  lockVerticalRotation?: boolean
}

export function useGlassScene(
  container: HTMLElement,
  data: Glass3DData,
  options: GlassSceneOptions = {},
): GlassScene {
  const t = data.glass_template
  const height = t.glass_height * SCALE
  const topR = t.top_radius * SCALE
  const botR = t.bottom_radius * SCALE
  const wallT = t.wall_thickness * SCALE
  const baseT = t.base_thickness * SCALE

  // Renderer
  const isTransparent = (options.backgroundColor ?? 0x111111) === -1
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance',
    preserveDrawingBuffer: isTransparent,
    premultipliedAlpha: false,
  })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(container.clientWidth, container.clientHeight)
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.0
  container.appendChild(renderer.domElement)

  // Scene
  const scene = new THREE.Scene()
  const bgColor = options.backgroundColor ?? 0x111111
  scene.background = bgColor === -1 ? null : new THREE.Color(bgColor)

  // Camera — position to frame the glass nicely
  const aspect = container.clientWidth / container.clientHeight
  const camera = new THREE.PerspectiveCamera(40, aspect, 0.01, 100)
  camera.position.set(0, height * 0.8, height * 3.2)
  camera.lookAt(0, height * 0.35, 0)

  // Controls
  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enablePan = false
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.autoRotate = true
  controls.autoRotateSpeed = 1.5
  controls.target.set(0, height * 0.35, 0)
  controls.minDistance = height * 0.8
  controls.maxDistance = height * 5
  controls.maxPolarAngle = Math.PI * 0.85
  if (options.lockVerticalRotation) {
    // Allow a narrow vertical range around a slightly-above-center view.
    const centerPolar = Math.PI * 0.55
    const spread = Math.PI * 0.08 // ~14° total
    controls.minPolarAngle = centerPolar - spread
    controls.maxPolarAngle = centerPolar + spread
  }
  controls.update()

  // Lighting
  const ambient = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambient)

  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8)
  dirLight.position.set(0.5, 2, 1)
  scene.add(dirLight)

  const spotLight = new THREE.SpotLight(0xffffff, 0.6, 0, Math.PI / 6, 0.5, 1)
  spotLight.position.set(-0.3, height * 3, 0.5)
  spotLight.target.position.set(0, height * 0.5, 0)
  scene.add(spotLight)
  scene.add(spotLight.target)

  // ─── Wrap layer (the vinyl design) ───
  // The backend sends a warped sector SVG (same as the designer).
  // The sector represents the full 360° glass circumference unwrapped.
  // We "unwrap" it back to a rectangle that maps to a full cylinder.

  const wrapMat = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0,
    side: THREE.DoubleSide,
    roughness: 0.4,
    metalness: 0,
    depthWrite: false,
  })

  // Full cylinder for the wrap (covers 360°)
  const wrapGeo = new THREE.CylinderGeometry(
    topR + 0.001, botR + 0.001, height, 64, 1, true,
  )
  const wrapMesh = new THREE.Mesh(wrapGeo, wrapMat)
  wrapMesh.position.y = height / 2
  wrapMesh.renderOrder = 1
  scene.add(wrapMesh)

  // Load sector SVG, unwrap it to a rectangle, and apply as cylinder texture.
  unwrapSectorToTexture(data.wrap_svg, t).then((texture) => {
    wrapMat.map = texture
    wrapMat.opacity = 1
    wrapMat.alphaTest = 0.05
    wrapMat.needsUpdate = true
    needsRender = true
  })

  // ─── Glass shell (transparent overlay for glassy look) ───
  // Slightly larger cylinder on top of the wrap to add glass-like
  // reflections, glare, and transparency without hiding the wrap.
  const glassGeo = new THREE.CylinderGeometry(
    topR + 0.002, botR + 0.002, height, 64, 1, true,
  )
  const glassMat = new THREE.MeshPhysicalMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.08,
    roughness: 0.02,
    metalness: 0,
    clearcoat: 1.0,
    clearcoatRoughness: 0.03,
    ior: 1.5,
    side: THREE.FrontSide, // only outer surface for glare
    depthWrite: false, // don't occlude the wrap underneath
  })
  const glassMesh = new THREE.Mesh(glassGeo, glassMat)
  glassMesh.position.y = height / 2
  glassMesh.renderOrder = 2 // render after wrap
  scene.add(glassMesh)

  // Glass base
  const baseGeo = new THREE.CircleGeometry(botR, 64)
  const baseMat = new THREE.MeshPhysicalMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.15,
    roughness: 0.1,
    clearcoat: 0.5,
    ior: 1.5,
    side: THREE.DoubleSide,
  })
  const baseMesh = new THREE.Mesh(baseGeo, baseMat)
  baseMesh.rotation.x = -Math.PI / 2
  baseMesh.position.y = 0.001
  scene.add(baseMesh)

  // Glass rim — thin torus for visual definition
  const rimGeo = new THREE.TorusGeometry(topR, wallT * 0.4, 8, 64)
  const rimMat = new THREE.MeshPhysicalMaterial({
    color: 0xdddddd,
    transparent: true,
    opacity: 0.35,
    roughness: 0.05,
    clearcoat: 1.0,
    ior: 1.5,
  })
  const rimMesh = new THREE.Mesh(rimGeo, rimMat)
  rimMesh.rotation.x = Math.PI / 2
  rimMesh.position.y = height
  scene.add(rimMesh)

  // ─── Beer liquid ───
  let beerMesh: THREE.Mesh | null = null
  let foamMesh: THREE.Mesh | null = null
  let currentBeerFrac = 0.0 // 0 = rim (full), 1 = base (empty)
  let targetBeerFrac = 0.0
  let animating = false

  const beerMat = new THREE.MeshPhysicalMaterial({
    color: 0xF5C842,  // golden lager
    transparent: true,
    opacity: 0.62,
    roughness: 0.15,
    metalness: 0,
    transmission: 0.45,
    thickness: 2,
    side: THREE.DoubleSide,
  })

  // Beer head (foam) material — creamy white, opaque
  const headMat = new THREE.MeshStandardMaterial({
    color: 0xFFF8E8,
    transparent: true,
    opacity: 0.92,
    roughness: 0.95,
    metalness: 0,
    side: THREE.DoubleSide,
  })

  const foamMat = new THREE.MeshStandardMaterial({
    color: 0xFFF5E0,
    transparent: true,
    opacity: 0.75,
    roughness: 0.9,
    side: THREE.DoubleSide,
  })

  // ─── Bubbles (3D spheres inside the beer) ───
  const BUBBLE_COUNT = 35
  const bubbles: { mesh: THREE.Mesh; speed: number; phase: number; wobbleSpeed: number }[] = []

  function spawnBubble(maxY: number): { mesh: THREE.Mesh; speed: number; phase: number; wobbleSpeed: number } {
    // Random size — mostly tiny, a few larger
    const radius = 0.002 + Math.random() * Math.random() * 0.008
    const geo = new THREE.SphereGeometry(radius, 8, 8)
    const mat = new THREE.MeshPhysicalMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.25 + Math.random() * 0.2,
      roughness: 0.0,
      metalness: 0.1,
      transmission: 0.6,
      ior: 1.33,
    })
    const mesh = new THREE.Mesh(geo, mat)

    // Position inside the glass at a random point
    const innerBotR2 = botR - wallT
    const angle = Math.random() * Math.PI * 2
    const r = innerBotR2 * (0.1 + Math.random() * 0.5)
    mesh.position.set(
      Math.cos(angle) * r,
      baseT + Math.random() * Math.max(0.01, maxY - baseT) * 0.5,
      Math.sin(angle) * r,
    )
    mesh.visible = false
    scene.add(mesh)

    return {
      mesh,
      speed: 0.0002 + Math.random() * 0.0005,
      phase: Math.random() * Math.PI * 2,
      wobbleSpeed: 0.001 + Math.random() * 0.003,
    }
  }

  function initBubbles() {
    for (let i = 0; i < BUBBLE_COUNT; i++) {
      bubbles.push(spawnBubble(height * 0.8))
    }
  }
  initBubbles()

  function updateBubbles(beerFrac: number, time: number) {
    const baseFrac2 = baseT / height
    const beerTopPos2 = Math.max(0, 1 - beerFrac - baseFrac2) / (1 - baseFrac2)
    if (beerTopPos2 <= 0.01) {
      for (const b of bubbles) b.mesh.visible = false
      return
    }
    const innerH = height - baseT
    const beerTop = baseT + innerH * beerTopPos2
    const innerBotR2 = botR - wallT
    const innerTopR2 = topR - wallT

    for (const b of bubbles) {
      // Rise
      b.mesh.position.y += b.speed

      // Gentle wobble in x and z
      b.mesh.position.x += Math.sin(time * b.wobbleSpeed + b.phase) * 0.0002
      b.mesh.position.z += Math.cos(time * b.wobbleSpeed * 0.7 + b.phase) * 0.0002

      // Clamp radius to stay inside the tapered glass at current height
      const hFrac = Math.max(0, (b.mesh.position.y - baseT) / innerH)
      const maxR = (innerBotR2 + (innerTopR2 - innerBotR2) * hFrac) * 0.7
      const curR = Math.sqrt(b.mesh.position.x ** 2 + b.mesh.position.z ** 2)
      if (curR > maxR && curR > 0) {
        b.mesh.position.x *= maxR / curR
        b.mesh.position.z *= maxR / curR
      }

      // Reset at beer surface
      if (b.mesh.position.y > beerTop - 0.005) {
        b.mesh.position.y = baseT + Math.random() * 0.02
        const angle = Math.random() * Math.PI * 2
        const r = innerBotR2 * (0.1 + Math.random() * 0.5)
        b.mesh.position.x = Math.cos(angle) * r
        b.mesh.position.z = Math.sin(angle) * r
      }

      b.mesh.visible = b.mesh.position.y < beerTop && b.mesh.position.y > baseT
    }
  }

  let headMesh: THREE.Mesh | null = null

  function buildBeerGeometry(beerFrac: number) {
    // beerFrac: 0 = rim (full glass), 1 = base (empty glass)
    // This is a fraction of the TOTAL glass height, not inner height.
    const innerTopR = topR - wallT
    const innerBotR = botR - wallT
    const innerHeight = height - baseT

    // Convert glass-height fraction to inner-height fraction
    // beerFrac=0 → beer fills all inner height, beerFrac=1 → no beer
    // The base takes up baseT/height of the total, beer can't go below that
    const baseFrac = baseT / height
    const beerTopPos = Math.max(0, 1 - beerFrac - baseFrac) / (1 - baseFrac)
    const beerTopFrac = Math.max(0, Math.min(1, beerTopPos))

    if (beerTopFrac <= 0.01) {
      if (beerMesh) {
        scene.remove(beerMesh)
        beerMesh.geometry.dispose()
        beerMesh = null
      }
      if (foamMesh) {
        scene.remove(foamMesh)
        foamMesh.geometry.dispose()
        foamMesh = null
      }
      if (headMesh) {
        scene.remove(headMesh)
        headMesh.geometry.dispose()
        headMesh = null
      }
      return
    }

    const beerH = innerHeight * beerTopFrac
    const beerTopR = innerBotR + (innerTopR - innerBotR) * beerTopFrac

    // Head thickness — proportional to beer amount, thicker when fuller
    const headThickness = Math.min(0.06, beerH * 0.04)
    const beerBodyH = beerH - headThickness

    if (beerMesh) {
      scene.remove(beerMesh)
      beerMesh.geometry.dispose()
    }
    if (foamMesh) {
      scene.remove(foamMesh)
      foamMesh.geometry.dispose()
    }
    if (headMesh) {
      scene.remove(headMesh)
      headMesh.geometry.dispose()
    }

    // Beer body (below the head)
    if (beerBodyH > 0.001) {
      const bodyTopR = innerBotR + (innerTopR - innerBotR) * (beerBodyH / innerHeight)
      const geo = new THREE.CylinderGeometry(bodyTopR, innerBotR, beerBodyH, 64, 1, false)
      beerMesh = new THREE.Mesh(geo, beerMat)
      beerMesh.position.y = baseT + beerBodyH / 2
      beerMesh.renderOrder = 1
      scene.add(beerMesh)
    }

    // Beer head (foam layer on top)
    if (headThickness > 0.001) {
      const headBotR = innerBotR + (innerTopR - innerBotR) * (beerBodyH / innerHeight)
      const headGeo = new THREE.CylinderGeometry(beerTopR, headBotR, headThickness, 64, 1, false)
      headMesh = new THREE.Mesh(headGeo, headMat)
      headMesh.position.y = baseT + beerBodyH + headThickness / 2
      headMesh.renderOrder = 1
      scene.add(headMesh)
    }

    // Thin foam disc on very top for surface definition
    const foamGeo = new THREE.CylinderGeometry(beerTopR, beerTopR, 0.002, 64, 1, false)
    foamMesh = new THREE.Mesh(foamGeo, foamMat)
    foamMesh.position.y = baseT + beerH
    foamMesh.renderOrder = 1
    scene.add(foamMesh)
  }

  // Start with full beer
  buildBeerGeometry(0.0)

  // Environment map for reflections on the glass shell
  const envScene = new THREE.Scene()
  envScene.background = new THREE.Color(0x333333)
  const pmremGenerator = new THREE.PMREMGenerator(renderer)
  const envMap = pmremGenerator.fromScene(envScene).texture
  glassMat.envMap = envMap
  glassMat.envMapIntensity = 0.5
  pmremGenerator.dispose()

  // ─── Animation loop ───
  let needsRender = true
  let animFrame: number
  let disposed = false

  controls.addEventListener('change', () => { needsRender = true })

  let frameCount = 0

  function animate() {
    if (disposed) return
    animFrame = requestAnimationFrame(animate)
    frameCount++

    if (animating) {
      const diff = targetBeerFrac - currentBeerFrac
      if (Math.abs(diff) < 0.002) {
        currentBeerFrac = targetBeerFrac
        animating = false
      } else {
        currentBeerFrac += diff * 0.04
      }
      buildBeerGeometry(currentBeerFrac)
      needsRender = true
    }

    // Animate bubbles every frame
    updateBubbles(currentBeerFrac, frameCount)
    needsRender = true // bubbles always need re-render

    controls.update()

    if (needsRender || controls.autoRotate) {
      renderer.render(scene, camera)
      needsRender = false
    }
  }
  animate()

  // Resize
  function onResize() {
    if (disposed) return
    const w = container.clientWidth
    const h = container.clientHeight
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
    needsRender = true
  }

  const resizeObserver = new ResizeObserver(onResize)
  resizeObserver.observe(container)

  // Public API
  function updateBeerLevel(
    scores: Record<number, number>,
    holes: { number: number; par: number }[],
    glassNumber: number,
  ) {
    const newFrac = computeBeerHeight(
      scores, holes, data.zones_by_hole, data.holes_per_glass, glassNumber,
    )
    targetBeerFrac = newFrac
    animating = true
    needsRender = true
  }

  function dispose() {
    disposed = true
    cancelAnimationFrame(animFrame)
    resizeObserver.disconnect()
    controls.dispose()

    scene.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry.dispose()
        if (Array.isArray(obj.material)) {
          obj.material.forEach(m => m.dispose())
        } else {
          obj.material.dispose()
        }
      }
    })

    envMap.dispose()
    renderer.dispose()
    if (renderer.domElement.parentElement) {
      container.removeChild(renderer.domElement)
    }
  }

  return { updateBeerLevel, dispose }
}

/**
 * Render a sector-shaped SVG to an Image element.
 */
function renderSvgToImage(svgString: string): Promise<{ img: HTMLImageElement; vbX: number; vbY: number; vbW: number; vbH: number }> {
  return new Promise((resolve, reject) => {
    const vbMatch = svgString.match(/viewBox\s*=\s*"([^"]+)"/)
    let vbX = 0, vbY = 0, vbW = 900, vbH = 700
    if (vbMatch) {
      const parts = vbMatch[1].trim().split(/[\s,]+/).map(Number)
      if (parts.length >= 4) {
        [vbX, vbY, vbW, vbH] = parts
      }
    }

    // Ensure explicit width/height for Image rendering
    let fixedSvg = svgString
    const pixW = Math.round(vbW * 4) // high-res source
    const pixH = Math.round(vbH * 4)
    if (!/\bwidth\s*=/.test(fixedSvg)) {
      fixedSvg = fixedSvg.replace('<svg', `<svg width="${pixW}" height="${pixH}"`)
    } else {
      fixedSvg = fixedSvg
        .replace(/\bwidth\s*=\s*"[^"]*"/, `width="${pixW}"`)
        .replace(/\bheight\s*=\s*"[^"]*"/, `height="${pixH}"`)
    }

    const img = new Image()
    const blob = new Blob([fixedSvg], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)

    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve({ img, vbX, vbY, vbW, vbH })
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Failed to load SVG as image'))
    }
    img.src = url
  })
}

/**
 * Unwrap a sector-shaped SVG into a rectangular texture for a cylinder.
 *
 * The sector SVG represents the full 360° glass circumference unwrapped
 * as a cone sector (arc shape). To map it onto a CylinderGeometry, we
 * sample each (u, v) point on the cylinder, compute where it falls in
 * the sector's polar coordinate space, and copy that pixel.
 *
 * Cylinder UV mapping:
 *   U = 0→1 around circumference (0→2π)
 *   V = 0→1 from bottom to top
 *
 * Sector geometry:
 *   angle ∈ [-halfAngle, +halfAngle]  (maps to full 360° circumference)
 *   radius ∈ [inner_r, outer_r]       (maps to base→rim)
 *   x = r·sin(angle), y = -r·cos(angle)
 */
async function unwrapSectorToTexture(
  svgString: string,
  template: import('../types/glass3d').GlassTemplate,
): Promise<THREE.CanvasTexture> {
  const { img, vbX, vbY, vbW, vbH } = await renderSvgToImage(svgString)

  const innerR = template.inner_r
  const outerR = template.outer_r
  const halfAngle = template.sector_angle / 2

  // Render SVG to source canvas
  const srcW = img.naturalWidth || Math.round(vbW * 4)
  const srcH = img.naturalHeight || Math.round(vbH * 4)
  const srcCanvas = document.createElement('canvas')
  srcCanvas.width = srcW
  srcCanvas.height = srcH
  const srcCtx = srcCanvas.getContext('2d')!
  srcCtx.drawImage(img, 0, 0, srcW, srcH)
  const srcData = srcCtx.getImageData(0, 0, srcW, srcH)

  // Create destination rectangle (maps to cylinder UVs)
  const dstW = 2048
  const dstH = 1024
  const dstCanvas = document.createElement('canvas')
  dstCanvas.width = dstW
  dstCanvas.height = dstH
  const dstCtx = dstCanvas.getContext('2d')!
  const dstData = dstCtx.createImageData(dstW, dstH)

  // For each destination pixel (u, v), find the source pixel
  for (let dy = 0; dy < dstH; dy++) {
    // V: 0 = bottom (inner_r), 1 = top (outer_r) — but cylinder V=0 is bottom
    const v = dy / dstH
    // Map V to radius: top of texture (dy=0) = rim (outer_r), bottom = base (inner_r)
    const r = outerR - v * (outerR - innerR)

    for (let dx = 0; dx < dstW; dx++) {
      // U: 0→1 around circumference
      const u = dx / dstW
      // Map U to angle within sector
      const angle = -halfAngle + u * (halfAngle * 2)

      // Convert polar to cartesian (SVG coordinate space)
      const sx = r * Math.sin(angle)
      const sy = -r * Math.cos(angle)

      // Map SVG coords to source canvas pixel coords
      const srcPx = ((sx - vbX) / vbW) * srcW
      const srcPy = ((sy - vbY) / vbH) * srcH

      // Bounds check
      const srcPxI = Math.round(srcPx)
      const srcPyI = Math.round(srcPy)
      if (srcPxI < 0 || srcPxI >= srcW || srcPyI < 0 || srcPyI >= srcH) continue

      // Copy pixel
      const srcIdx = (srcPyI * srcW + srcPxI) * 4
      const dstIdx = (dy * dstW + dx) * 4
      dstData.data[dstIdx] = srcData.data[srcIdx]
      dstData.data[dstIdx + 1] = srcData.data[srcIdx + 1]
      dstData.data[dstIdx + 2] = srcData.data[srcIdx + 2]
      dstData.data[dstIdx + 3] = srcData.data[srcIdx + 3]
    }
  }

  dstCtx.putImageData(dstData, 0, 0)

  const texture = new THREE.CanvasTexture(dstCanvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.ClampToEdgeWrapping
  texture.needsUpdate = true
  return texture
}
