import type { HoleZones, ScoringZone } from '../types/glass3d'

/**
 * Compute the beer fill height fraction for the 3D glass.
 *
 * Returns a value where 0.0 = rim (full glass) and 1.0 = base (empty glass).
 * The beer level corresponds to the last scored hole's score position
 * on the ruler, using the "above green" zone when duplicates exist.
 */
export function computeBeerHeight(
  scores: Record<number, number>,
  holes: { number: number; par: number }[],
  zonesByHole: HoleZones[],
  holesPerGlass: number,
  glassNumber: number,
): number {
  const startHole = (glassNumber - 1) * holesPerGlass + 1
  const endHole = startHole + holesPerGlass - 1

  // Find the highest-numbered hole on this glass that has a score
  let lastScoredHoleNum = -1
  for (let h = startHole; h <= endHole; h++) {
    if (scores[h] !== undefined) {
      lastScoredHoleNum = h
    }
  }

  if (lastScoredHoleNum === -1) return 0.0

  const holeInfo = holes.find(h => h.number === lastScoredHoleNum)
  const par = holeInfo?.par ?? 4
  const score = scores[lastScoredHoleNum]
  const relToPar = score - par

  const holeZones = zonesByHole.find(z => z.hole_ref === lastScoredHoleNum)
  if (!holeZones || holeZones.zones.length === 0) return 0.0

  // Find the best matching zone for this score.
  // Some zones get merged (e.g., +0 and +1 merge into +3 on short holes),
  // so we can't always find an exact match. Use the closest zone instead.
  const aboveZones = holeZones.zones.filter(z => z.position === 'above')
  const greenZone = holeZones.zones.find(z => z.position === 'green')

  // For eagle/birdie, use the green zone
  if (relToPar <= -1 && greenZone) {
    return greenZone.height_frac_bottom
  }

  // For above-par scores, find the exact or closest "above" zone
  if (aboveZones.length > 0) {
    // Try exact match first
    const exact = aboveZones.find(z => z.score === relToPar)
    if (exact) return exact.height_frac_bottom

    // No exact match — find the zone with the closest score
    // Sort by how close the zone score is to our relToPar
    const sorted = [...aboveZones].sort(
      (a, b) => Math.abs(a.score - relToPar) - Math.abs(b.score - relToPar)
    )
    const closest = sorted[0]

    // If our score falls between two zones, interpolate position
    // Find the zones just above and just below our score
    const zonesDescending = [...aboveZones].sort((a, b) => b.score - a.score)
    let zoneAbove: ScoringZone | undefined
    let zoneBelow: ScoringZone | undefined
    for (const z of zonesDescending) {
      if (z.score >= relToPar && (!zoneAbove || z.score < zoneAbove.score)) {
        zoneAbove = z
      }
      if (z.score <= relToPar && (!zoneBelow || z.score > zoneBelow.score)) {
        zoneBelow = z
      }
    }

    if (zoneAbove && zoneBelow && zoneAbove !== zoneBelow) {
      // Interpolate between the two bounding zones
      const range = zoneAbove.score - zoneBelow.score
      const t = range > 0 ? (relToPar - zoneBelow.score) / range : 0.5
      return zoneBelow.height_frac_bottom + t * (zoneAbove.height_frac_bottom - zoneBelow.height_frac_bottom)
    }

    return closest.height_frac_bottom
  }

  // Fallback: use the last zone's bottom
  return holeZones.zones[holeZones.zones.length - 1].height_frac_bottom
}
