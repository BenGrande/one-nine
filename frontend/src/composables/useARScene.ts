import * as THREE from 'three'
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js'
import type { Glass3DData } from '../types/glass3d'
import { computeBeerHeight } from './useGlassBeerLevel'

const SCALE = 0.01

/**
 * Build a simple Three.js scene of the glass for GLB export.
 * Uses basic materials (no transmission/physical) for max AR compatibility.
 */
function buildExportScene(data: Glass3DData, beerFrac: number): THREE.Scene {
  const t = data.glass_template
  // AR models are in meters — scale mm to m (0.001)
  const s = 0.001
  const height = t.glass_height * s
  const topR = t.top_radius * s
  const botR = t.bottom_radius * s
  const wallT = t.wall_thickness * s
  const baseT = t.base_thickness * s

  const scene = new THREE.Scene()

  // Glass shell
  const glassGeo = new THREE.CylinderGeometry(topR, botR, height, 64, 1, true)
  const glassMat = new THREE.MeshStandardMaterial({
    color: 0xddeeff,
    transparent: true,
    opacity: 0.2,
    roughness: 0.05,
    metalness: 0.1,
    side: THREE.DoubleSide,
  })
  const glassMesh = new THREE.Mesh(glassGeo, glassMat)
  glassMesh.position.y = height / 2
  scene.add(glassMesh)

  // Base
  const baseGeo = new THREE.CircleGeometry(botR, 64)
  const baseMesh = new THREE.Mesh(baseGeo, glassMat.clone())
  baseMesh.material.opacity = 0.3
  baseMesh.rotation.x = -Math.PI / 2
  baseMesh.position.y = 0.001
  scene.add(baseMesh)

  // Rim
  const rimGeo = new THREE.TorusGeometry(topR, wallT * 0.4, 8, 64)
  const rimMat = new THREE.MeshStandardMaterial({
    color: 0xcccccc,
    transparent: true,
    opacity: 0.5,
    roughness: 0.05,
  })
  const rimMesh = new THREE.Mesh(rimGeo, rimMat)
  rimMesh.rotation.x = Math.PI / 2
  rimMesh.position.y = height
  scene.add(rimMesh)

  // Beer
  const innerTopR = topR - wallT
  const innerBotR = botR - wallT
  const innerHeight = height - baseT
  const baseFracR = baseT / height
  const beerTopPos = Math.max(0, 1 - beerFrac - baseFracR) / (1 - baseFracR)

  if (beerTopPos > 0.01) {
    const beerH = innerHeight * beerTopPos
    const beerTopR = innerBotR + (innerTopR - innerBotR) * beerTopPos
    const headThickness = Math.min(0.005, beerH * 0.04)
    const beerBodyH = beerH - headThickness

    if (beerBodyH > 0.0005) {
      const bodyTopR = innerBotR + (innerTopR - innerBotR) * (beerBodyH / innerHeight)
      const beerGeo = new THREE.CylinderGeometry(bodyTopR, innerBotR, beerBodyH, 64, 1, false)
      const beerMat = new THREE.MeshStandardMaterial({
        color: 0xF5C842,
        transparent: true,
        opacity: 0.75,
        roughness: 0.2,
        side: THREE.DoubleSide,
      })
      const beerMesh = new THREE.Mesh(beerGeo, beerMat)
      beerMesh.position.y = baseT + beerBodyH / 2
      scene.add(beerMesh)
    }

    if (headThickness > 0.0005) {
      const headBotR = innerBotR + (innerTopR - innerBotR) * (beerBodyH / innerHeight)
      const headGeo = new THREE.CylinderGeometry(beerTopR, headBotR, headThickness, 64, 1, false)
      const headMat = new THREE.MeshStandardMaterial({
        color: 0xFFF8E8,
        roughness: 0.95,
        side: THREE.DoubleSide,
      })
      const headMesh = new THREE.Mesh(headGeo, headMat)
      headMesh.position.y = baseT + beerBodyH + headThickness / 2
      scene.add(headMesh)
    }
  }

  return scene
}

/**
 * Export scene to GLB blob.
 */
async function exportToGLB(scene: THREE.Scene): Promise<Blob> {
  const exporter = new GLTFExporter()
  return new Promise((resolve, reject) => {
    exporter.parse(
      scene,
      (result) => {
        if (result instanceof ArrayBuffer) {
          resolve(new Blob([result], { type: 'model/gltf-binary' }))
        } else {
          reject(new Error('Expected binary output'))
        }
      },
      (error) => reject(error),
      { binary: true },
    )
  })
}

interface ARScene {
  start: () => Promise<boolean>
  stop: () => void
  updateBeerLevel: (
    scores: Record<number, number>,
    holes: { number: number; par: number }[],
    glassNumber: number,
  ) => void
  isSupported: () => Promise<boolean>
}

export function useARScene(
  _container: HTMLElement,
  data: Glass3DData,
): ARScene {
  let currentBeerFrac = 0.0
  let overlayEl: HTMLElement | null = null
  let blobUrl: string | null = null

  async function isSupported(): Promise<boolean> {
    // model-viewer supports AR on iOS (Quick Look) and Android (Scene Viewer / WebXR)
    // Just check if we're on a mobile device
    const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
    return isMobile
  }

  async function start(): Promise<boolean> {
    try {
      // Ensure model-viewer is loaded
      await import('@google/model-viewer')

      // Build and export the glass
      const scene = buildExportScene(data, currentBeerFrac)
      const glb = await exportToGLB(scene)

      // Dispose export scene
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh) {
          obj.geometry.dispose()
          if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose())
          else obj.material.dispose()
        }
      })

      blobUrl = URL.createObjectURL(glb)

      // Create fullscreen overlay with model-viewer
      overlayEl = document.createElement('div')
      overlayEl.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:10000;background:#111'

      overlayEl.innerHTML = `
        <model-viewer
          src="${blobUrl}"
          ar
          ar-modes="scene-viewer webxr quick-look"
          camera-controls
          auto-rotate
          shadow-intensity="1"
          style="width:100%;height:100%;background:#111"
        >
          <button slot="ar-button" style="
            position:absolute;bottom:24px;left:50%;transform:translateX(-50%);
            padding:12px 28px;background:rgba(5,150,105,0.9);color:white;
            border:none;border-radius:999px;font-size:14px;font-weight:600;
            cursor:pointer;backdrop-filter:blur(4px);
          ">
            View on your table
          </button>
        </model-viewer>
        <button id="ar-close" style="
          position:absolute;top:16px;right:16px;z-index:10001;
          padding:8px 16px;background:rgba(0,0,0,0.7);color:white;
          border:1px solid rgba(255,255,255,0.3);border-radius:999px;
          font-size:12px;cursor:pointer;backdrop-filter:blur(4px);
        ">Close</button>
      `

      document.body.appendChild(overlayEl)

      // Close button handler
      overlayEl.querySelector('#ar-close')?.addEventListener('click', stop)

      // Auto-activate AR after model loads
      const mv = overlayEl.querySelector('model-viewer') as any
      if (mv) {
        mv.addEventListener('load', () => {
          // Try to auto-activate AR
          setTimeout(() => mv.activateAR?.(), 500)
        })
      }

      return true
    } catch (e) {
      console.error('AR failed:', e)
      return false
    }
  }

  function stop() {
    if (overlayEl) {
      document.body.removeChild(overlayEl)
      overlayEl = null
    }
    if (blobUrl) {
      URL.revokeObjectURL(blobUrl)
      blobUrl = null
    }
  }

  function updateBeerLevel(
    scores: Record<number, number>,
    holes: { number: number; par: number }[],
    glassNumber: number,
  ) {
    currentBeerFrac = computeBeerHeight(
      scores, holes, data.zones_by_hole, data.holes_per_glass, glassNumber,
    )
  }

  return { start, stop, updateBeerLevel, isSupported }
}
