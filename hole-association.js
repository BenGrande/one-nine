// Spatial association of OSM features to holes
// Takes raw course map data and returns per-hole feature bundles

function distSq(a, b) {
  const dlat = a[0] - b[0];
  const dlon = a[1] - b[1];
  return dlat * dlat + dlon * dlon;
}

function minDistToPolyline(point, polyline) {
  let best = Infinity;
  for (const p of polyline) {
    const d = distSq(point, p);
    if (d < best) best = d;
  }
  return Math.sqrt(best);
}

function minDistBetween(coords1, coords2) {
  let best = Infinity;
  for (const a of coords1) {
    for (const b of coords2) {
      const d = distSq(a, b);
      if (d < best) best = d;
    }
  }
  return Math.sqrt(best);
}

function centroid(coords) {
  let lat = 0, lon = 0;
  for (const [la, lo] of coords) {
    lat += la;
    lon += lo;
  }
  return [lat / coords.length, lon / coords.length];
}

// Compute a bounding box for a set of coords with padding
function bbox(coords, pad = 0) {
  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
  for (const [lat, lon] of coords) {
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
  }
  return {
    minLat: minLat - pad,
    maxLat: maxLat + pad,
    minLon: minLon - pad,
    maxLon: maxLon + pad,
  };
}

function bboxOverlaps(a, b) {
  return a.minLat <= b.maxLat && a.maxLat >= b.minLat &&
         a.minLon <= b.maxLon && a.maxLon >= b.minLon;
}

/**
 * Associate features with holes.
 *
 * @param {Array} features - Raw features from course-map endpoint
 * @param {Object} courseData - Course data from golf API (for par/yardage/handicap)
 * @returns {Array} Array of hole objects with associated features
 */
function associateFeatures(features, courseData) {
  const holes = features
    .filter((f) => f.category === "hole" && f.ref)
    .sort((a, b) => Number(a.ref) - Number(b.ref));

  const otherFeatures = features.filter(
    (f) => f.category !== "hole" && f.category !== "course_boundary"
  );

  if (holes.length === 0) return [];

  // Compute distance from each feature to each hole
  // Use generous padding for bbox pre-filter
  const holeBboxes = holes.map((h) => bbox(h.coords, 0.002));

  // For multi-hole features (like water), we use a threshold.
  // The threshold is the median nearest-hole distance * multiplier.
  const PRIMARY_MULTIPLIER = 3;

  const holeFeatureMap = new Map();
  for (const h of holes) {
    holeFeatureMap.set(h.ref, []);
  }

  for (const feat of otherFeatures) {
    // Skip cart paths entirely
    if (feat.category === "path") continue;
    const featBbox = bbox(feat.coords, 0.001);

    // Calculate distance to each hole
    const distances = [];
    for (let i = 0; i < holes.length; i++) {
      // Quick bbox pre-filter
      if (!bboxOverlaps(featBbox, holeBboxes[i])) {
        distances.push({ hole: holes[i], dist: Infinity });
        continue;
      }
      const d = minDistBetween(feat.coords, holes[i].coords);
      distances.push({ hole: holes[i], dist: d });
    }

    distances.sort((a, b) => a.dist - b.dist);
    const nearest = distances[0];

    if (nearest.dist === Infinity) continue;

    // Assign to nearest hole only
    holeFeatureMap.get(nearest.hole.ref).push({
      ...feat,
      _distToHole: nearest.dist,
    });
  }

  // Look up par/yardage/handicap from the golf course API data
  const apiHoles = getApiHoleData(courseData);

  // Build the result
  const result = holes.map((hole) => {
    const ref = Number(hole.ref);
    const apiHole = apiHoles[ref - 1] || {};

    // Difficulty score: lower = harder = steeper angle
    // Use handicap if available, otherwise derive from par/yardage
    let difficulty;
    if (apiHole.handicap) {
      difficulty = apiHole.handicap; // 1 = hardest, 18 = easiest
    } else if (hole.par && apiHole.yardage) {
      // Compute relative difficulty: yardage per par stroke
      // Higher ratio = harder relative to par
      difficulty = estimateDifficulty(hole.par, apiHole.yardage);
    } else {
      difficulty = 9; // neutral default
    }

    return {
      ref,
      par: hole.par || apiHole.par || null,
      yardage: apiHole.yardage || null,
      handicap: apiHole.handicap || null,
      difficulty,
      routeCoords: hole.coords,
      features: holeFeatureMap.get(hole.ref) || [],
    };
  });

  return result;
}

/**
 * Extract hole-by-hole data from the golf course API response.
 * Uses the longest male tee set.
 */
function getApiHoleData(courseData) {
  if (!courseData || !courseData.tees) return [];

  const maleTees = courseData.tees.male || [];
  const femaleTees = courseData.tees.female || [];
  const allTees = [...maleTees, ...femaleTees];

  if (allTees.length === 0) return [];

  // Pick the longest tee set
  const primary =
    maleTees.length > 0
      ? maleTees.reduce((a, b) => (a.total_yards > b.total_yards ? a : b))
      : allTees.reduce((a, b) => (a.total_yards > b.total_yards ? a : b));

  return primary.holes || [];
}

/**
 * Estimate difficulty rank (1-18) from par and yardage.
 * A short par 3 is easy (high rank number), a long par 4 is hard (low rank number).
 */
function estimateDifficulty(par, yardage) {
  // Expected yardage for each par
  const expected = { 3: 170, 4: 400, 5: 530 };
  const exp = expected[par] || 400;
  // Ratio > 1 means longer than expected = harder
  const ratio = yardage / exp;
  // Map ratio to difficulty rank: 1.3+ -> 1 (hardest), 0.7- -> 18 (easiest)
  const rank = Math.round(18 - (ratio - 0.7) * (17 / 0.6));
  return Math.max(1, Math.min(18, rank));
}

module.exports = { associateFeatures, getApiHoleData };
