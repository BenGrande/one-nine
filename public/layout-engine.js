// Layout Engine: positions holes flowing down a rectangular canvas
// Each hole is angled based on difficulty, length proportional to yardage

/**
 * Compute the layout for a set of holes on a rectangular canvas.
 */
function computeLayout(holes, opts) {
  const {
    canvasWidth = 900,
    canvasHeight = 700,
    marginX = 30,
    marginY = 30,
    textMargin = 60,
    maxHoleWidth = 0.55,
    holePadding = 0.02, // fraction of avg hole length to insert between holes
  } = opts || {};

  if (!holes || holes.length === 0) return { holes: [], canvasWidth, canvasHeight };

  const drawLeft = textMargin;
  const drawRight = canvasWidth - marginX;
  const drawTop = marginY;
  const drawBottom = canvasHeight - marginY;
  const drawWidth = drawRight - drawLeft;
  const drawHeight = drawBottom - drawTop;

  // Per-glass normalization: scale difficulty and yardage within THIS glass's holes
  const totalYardage = holes.reduce((s, h) => s + (h.yardage || 350), 0);
  const minAngle = 20;
  const maxAngle = 50;

  // Find difficulty range within this glass
  const difficulties = holes.map((h) => h.difficulty || 9);
  const minDiff = Math.min(...difficulties);
  const maxDiff = Math.max(...difficulties);
  const diffRange = maxDiff - minDiff || 1; // avoid division by zero

  const holeLayouts = holes.map((hole) => {
    const diff = hole.difficulty || 9;
    // Normalize within this glass's difficulty range (0 = hardest on this glass, 1 = easiest)
    const easyFactor = (diff - minDiff) / diffRange;
    const angleDeg = maxAngle - easyFactor * (maxAngle - minAngle);
    const angleRad = (angleDeg * Math.PI) / 180;
    const yardage = hole.yardage || 350;
    // Length proportional to this glass's total yardage
    const lengthFraction = yardage / totalYardage;
    return { hole, angleDeg, angleRad, lengthFraction, yardage };
  });

  // Simulate zigzag with gaps between holes
  const rawPositions = simulateZigzag(holeLayouts, holePadding);

  // Scale to fit canvas
  const totalVertical = rawPositions[rawPositions.length - 1].endY;
  const scaleFactor = drawHeight / totalVertical;

  // Map X: use drawWidth directly (zigzag X is already in [0,1] range)
  // Center the content horizontally without stretching
  let rawMinX = Infinity, rawMaxX = -Infinity;
  for (const rp of rawPositions) {
    rawMinX = Math.min(rawMinX, rp.startX, rp.endX);
    rawMaxX = Math.max(rawMaxX, rp.startX, rp.endX);
  }
  const rawSpan = rawMaxX - rawMinX || 0.5;
  const rawCenter = (rawMinX + rawMaxX) / 2;
  // Center in the draw area without stretching
  function mapX(nx) { return drawLeft + (nx - rawMinX + (1 - rawSpan) / 2) * drawWidth; }

  // Position and transform features
  const positioned = rawPositions.map((rp) => {
    const startX = mapX(rp.startX);
    const startY = drawTop + rp.startY * scaleFactor;
    const endX = mapX(rp.endX);
    const endY = drawTop + rp.endY * scaleFactor;
    const length = rp.rawLength * scaleFactor;
    const maxWidth = length * maxHoleWidth;

    const features = transformHoleFeatures(rp.hole, startX, startY, endX, endY, maxWidth);

    return {
      ref: rp.hole.ref,
      par: rp.hole.par,
      yardage: rp.yardage,
      handicap: rp.hole.handicap,
      difficulty: rp.hole.difficulty,
      startX, startY, endX, endY,
      angleDeg: rp.angleDeg,
      direction: rp.direction,
      length,
      features,
    };
  });

  // Post-pass: detect vertical overlaps and push holes down
  fixOverlaps(positioned);

  // Post-pass: scale content to fill the full draw area
  // Use VISIBLE content extent (features + label padding), not invisible routing endpoints
  let contentMinY = Infinity, contentMaxY = -Infinity;
  let contentMinX = Infinity, contentMaxX = -Infinity;
  for (const h of positioned) {
    // Label sits below tee: startY + ~12px
    contentMinY = Math.min(contentMinY, h.startY - 2);
    contentMaxY = Math.max(contentMaxY, h.startY + 14);
    contentMinX = Math.min(contentMinX, h.startX - 14);
    contentMaxX = Math.max(contentMaxX, h.startX + 14);
    for (const f of h.features) {
      for (const [x, y] of f.coords) {
        contentMinY = Math.min(contentMinY, y);
        contentMaxY = Math.max(contentMaxY, y);
        contentMinX = Math.min(contentMinX, x);
        contentMaxX = Math.max(contentMaxX, x);
      }
    }
  }
  const contentHeight = contentMaxY - contentMinY;
  const contentWidth = contentMaxX - contentMinX;
  if (contentHeight > 0) {
    // Scale to fill height, and also scale X proportionally
    const yRescale = drawHeight / contentHeight;
    const xRescale = drawWidth / contentWidth;
    // Use the smaller scale to preserve aspect ratio... actually we want to fill,
    // so scale Y to fill height and X to fill width independently
    for (const h of positioned) {
      h.startX = drawLeft + (h.startX - contentMinX) * xRescale;
      h.endX = drawLeft + (h.endX - contentMinX) * xRescale;
      h.startY = drawTop + (h.startY - contentMinY) * yRescale;
      h.endY = drawTop + (h.endY - contentMinY) * yRescale;
      h.length *= yRescale;
      for (const f of h.features) {
        for (const c of f.coords) {
          c[0] = drawLeft + (c[0] - contentMinX) * xRescale;
          c[1] = drawTop + (c[1] - contentMinY) * yRescale;
        }
      }
    }
  }

  // Post-pass: pack holes tight AFTER rescaling (removes gaps introduced by rescale)
  packHoles(positioned);

  return {
    holes: positioned,
    canvasWidth,
    canvasHeight,
    drawArea: { left: drawLeft, right: drawRight, top: drawTop, bottom: drawBottom },
  };
}

/**
 * Simulate zigzag in normalized space with gaps between holes.
 */
function simulateZigzag(holeLayouts, gapFraction) {
  const n = holeLayouts.length;
  const rawLengths = holeLayouts.map((h) => h.lengthFraction);
  const cosines = holeLayouts.map((h) => Math.cos(h.angleRad));
  const sines = holeLayouts.map((h) => Math.sin(h.angleRad));
  const avgLength = rawLengths.reduce((s, l) => s + l, 0) / n;
  const gap = avgLength * gapFraction;

  let curX = 0.12;
  let curY = 0;
  let direction = 1;
  let sweepAccum = 0;
  const targetSweep = n <= 3 ? 0.7 : n <= 6 ? 0.6 : 0.5;
  const result = [];

  for (let i = 0; i < n; i++) {
    const length = rawLengths[i];
    const dx = length * cosines[i];
    const dy = length * sines[i];
    let nextX = curX + dx * direction;
    sweepAccum += dx;

    if (nextX > 0.88 || nextX < 0.12 || (sweepAccum > targetSweep && i < n - 1)) {
      direction *= -1;
      nextX = curX + dx * direction;
      sweepAccum = dx;
    }

    result.push({
      ...holeLayouts[i],
      startX: curX,
      startY: curY,
      endX: nextX,
      endY: curY + dy,
      direction,
      rawLength: length,
    });

    curX = nextX;
    curY += dy;

    // Add gap before next hole
    if (i < n - 1) {
      curY += gap;
    }
  }

  return result;
}

/**
 * Post-pass: measure each hole's feature Y-extent and shift subsequent holes
 * down to eliminate any remaining overlap.
 */
function fixOverlaps(holes) {
  if (holes.length < 2) return;

  const minGap = 4;

  for (let i = 1; i < holes.length; i++) {
    const prev = holes[i - 1];
    const curr = holes[i];

    // Compute Y extent from FEATURES only (+ label padding), not routing endpoints
    let prevMaxY = prev.startY + 14; // label below tee
    for (const f of prev.features) {
      for (const [, y] of f.coords) {
        if (y > prevMaxY) prevMaxY = y;
      }
    }

    let currMinY = curr.startY - 2;
    for (const f of curr.features) {
      for (const [, y] of f.coords) {
        if (y < currMinY) currMinY = y;
      }
    }

    const overlap = prevMaxY + minGap - currMinY;
    if (overlap > 0) {
      // Shift this hole and all subsequent holes down
      for (let j = i; j < holes.length; j++) {
        holes[j].startY += overlap;
        holes[j].endY += overlap;
        for (const f of holes[j].features) {
          for (const c of f.coords) {
            c[1] += overlap;
          }
        }
      }
    }
  }
}

/**
 * Transform a hole's geo-coordinate features to canvas space.
 * Clamps features to a corridor around the routing line.
 */
/**
 * Post-pass: pack holes tight by removing excess vertical gaps.
 * Measures each hole's actual feature extent and shifts them up to close gaps.
 */
function packHoles(holes) {
  if (holes.length < 2) return;
  const targetGap = 4;

  for (let i = 1; i < holes.length; i++) {
    const prev = holes[i - 1];
    const curr = holes[i];

    // Measure previous hole's visual bottom
    let prevBottom = prev.startY + 14;
    for (const f of prev.features) {
      for (const [, y] of f.coords) prevBottom = Math.max(prevBottom, y);
    }

    // Measure current hole's visual top
    let currTop = curr.startY - 2;
    for (const f of curr.features) {
      for (const [, y] of f.coords) currTop = Math.min(currTop, y);
    }

    const currentGap = currTop - prevBottom;
    if (currentGap > targetGap) {
      const shift = -(currentGap - targetGap);
      for (let j = i; j < holes.length; j++) {
        holes[j].startY += shift;
        holes[j].endY += shift;
        for (const f of holes[j].features) {
          for (const c of f.coords) c[1] += shift;
        }
      }
    }
  }
}

function transformHoleFeatures(hole, startX, startY, endX, endY, maxWidth) {
  const route = hole.routeCoords;
  if (!route || route.length < 2) return [];

  const geoTee = route[0];
  const geoGreen = route[route.length - 1];
  const midLat = (geoTee[0] + geoGreen[0]) / 2;
  const cosLat = Math.cos(midLat * Math.PI / 180);

  const geoDx = (geoGreen[1] - geoTee[1]) * cosLat;
  // Negate latitude diff to convert from geo Y-up to canvas Y-down
  const geoDy = -(geoGreen[0] - geoTee[0]);
  const geoLen = Math.sqrt(geoDx * geoDx + geoDy * geoDy);
  if (geoLen === 0) return [];

  const canvasDx = endX - startX;
  const canvasDy = endY - startY;
  const canvasLen = Math.sqrt(canvasDx * canvasDx + canvasDy * canvasDy);
  if (canvasLen === 0) return [];

  let scale = canvasLen / geoLen;

  const geoAngle = Math.atan2(geoDy, geoDx);
  const canvasAngle = Math.atan2(canvasDy, canvasDx);
  const rotation = canvasAngle - geoAngle;
  const cosR = Math.cos(rotation);
  const sinR = Math.sin(rotation);

  // Global width clamping based on all features
  const coreCategories = new Set(["fairway", "green", "tee", "bunker", "rough"]);
  let minPerp = 0, maxPerp = 0;
  for (const f of hole.features) {
    if (!coreCategories.has(f.category)) continue;
    for (const [lat, lon] of f.coords) {
      const dx = (lon - geoTee[1]) * cosLat;
      const dy = -(lat - geoTee[0]);
      const perp = -dx * Math.sin(geoAngle) + dy * Math.cos(geoAngle);
      if (perp < minPerp) minPerp = perp;
      if (perp > maxPerp) maxPerp = perp;
    }
  }
  for (const [lat, lon] of route) {
    const dx = (lon - geoTee[1]) * cosLat;
    const dy = lat - geoTee[0];
    const perp = -dx * Math.sin(geoAngle) + dy * Math.cos(geoAngle);
    if (perp < minPerp) minPerp = perp;
    if (perp > maxPerp) maxPerp = perp;
  }

  const coreWidth = (maxPerp - minPerp) * scale;
  if (coreWidth > maxWidth && coreWidth > 0) {
    scale *= maxWidth / coreWidth;
  }

  // Corridor limits in canvas space for clamping
  const maxPerpCanvas = maxWidth * 0.6;
  const maxAlongCanvas = canvasLen * 1.15;
  const minAlongCanvas = -canvasLen * 0.15;

  // Unit vectors for the routing line in canvas space
  const ux = canvasDx / canvasLen;
  const uy = canvasDy / canvasLen;
  // Perpendicular unit vector
  const px = -uy;
  const py = ux;

  return hole.features.map((f) => {
    let fScale = scale;

    // Scale down water individually if too wide
    if (f.category === "water") {
      let fMinPerp = 0, fMaxPerp = 0;
      for (const [lat, lon] of f.coords) {
        const dx = (lon - geoTee[1]) * cosLat;
        const dy = -(lat - geoTee[0]);
        const perp = -dx * Math.sin(geoAngle) + dy * Math.cos(geoAngle);
        if (perp < fMinPerp) fMinPerp = perp;
        if (perp > fMaxPerp) fMaxPerp = perp;
      }
      const featWidth = (fMaxPerp - fMinPerp) * fScale;
      if (featWidth > maxPerpCanvas * 1.5 && featWidth > 0) {
        fScale = fScale * (maxPerpCanvas * 1.2) / featWidth;
      }
    }

    // Transform coordinates
    const coords = f.coords.map(([lat, lon]) => {
      const dx = (lon - geoTee[1]) * cosLat;
      const dy = -(lat - geoTee[0]);
      let rx = (dx * cosR - dy * sinR) * fScale;
      let ry = (dx * sinR + dy * cosR) * fScale;
      let cx = startX + rx;
      let cy = startY + ry;

      // Clamp to corridor: decompose into along/perp components from start point
      const along = (cx - startX) * ux + (cy - startY) * uy;
      const perp = (cx - startX) * px + (cy - startY) * py;

      const clampedAlong = Math.max(minAlongCanvas, Math.min(maxAlongCanvas, along));
      const clampedPerp = Math.max(-maxPerpCanvas, Math.min(maxPerpCanvas, perp));

      if (along !== clampedAlong || perp !== clampedPerp) {
        cx = startX + clampedAlong * ux + clampedPerp * px;
        cy = startY + clampedAlong * uy + clampedPerp * py;
      }

      return [cx, cy];
    });

    return {
      id: f.id,
      category: f.category,
      ref: f.ref,
      par: f.par,
      name: f.name,
      _shared: f._shared || false,
      coords,
    };
  });
}

/**
 * Split holes into glass groups.
 */
function splitIntoGlasses(holes, glassCount) {
  const n = holes.length;
  if (glassCount <= 1 || n <= 3) return [holes];

  if (glassCount === 2) {
    const mid = Math.ceil(n / 2);
    return [holes.slice(0, mid), holes.slice(mid)];
  }

  if (glassCount === 6 && n >= 18) {
    return [
      holes.slice(0, 3), holes.slice(3, 6), holes.slice(6, 9),
      holes.slice(9, 12), holes.slice(12, 15), holes.slice(15, 18),
    ];
  }

  const perGlass = Math.ceil(n / glassCount);
  const groups = [];
  for (let i = 0; i < n; i += perGlass) {
    groups.push(holes.slice(i, Math.min(i + perGlass, n)));
  }
  return groups;
}
