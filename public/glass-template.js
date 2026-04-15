// Glass Template Generator
// Generates the unwrapped vinyl wrap shape for a tapered pint glass.
//
// A pint glass is a truncated cone. When unwrapped, the surface is a sector
// of an annulus (ring) — a "fan" shape.
//
// Inputs: glass height, top circumference (from radius), bottom circumference.
// Output: SVG path for the wrap outline + a warp function to map rectangular
//         coordinates onto the tapered shape.

/**
 * Compute the unwrapped glass template geometry.
 *
 * @param {Object} opts
 * @param {number} opts.glassHeight - Height of the glass in mm
 * @param {number} opts.topRadius - Radius at the top (lip) of the glass in mm
 * @param {number} opts.bottomRadius - Radius at the bottom of the glass in mm
 * @returns {Object} Template geometry
 */
function computeGlassTemplate(opts) {
  const {
    glassHeight = 134.8,
    topRadius = 44.2,
    bottomRadius = 31.6,
    wallThickness = 3.1,
    baseThickness = 11.5,
  } = opts || {};

  const topCircumference = 2 * Math.PI * topRadius;
  const bottomCircumference = 2 * Math.PI * bottomRadius;

  // The glass is a truncated cone. The slant height:
  const radiusDiff = topRadius - bottomRadius;
  const slantHeight = Math.sqrt(glassHeight * glassHeight + radiusDiff * radiusDiff);

  // When unwrapped, the cone becomes a sector of an annulus.
  // The apex of the full cone is at distance D from the bottom:
  const D = (bottomRadius * slantHeight) / (topRadius - bottomRadius);

  // Inner radius of the annulus (bottom of glass):
  const innerR = D;
  // Outer radius (top of glass):
  const outerR = D + slantHeight;

  // The angle of the sector:
  // The arc length at the bottom = bottomCircumference = innerR * sectorAngle
  const sectorAngle = bottomCircumference / innerR; // in radians

  // The wrap SVG dimensions
  // We'll center the sector pointing upward, with the apex at the bottom
  const svgWidth = outerR * 2 * Math.sin(sectorAngle / 2) + 20;
  const svgHeight = outerR - innerR * Math.cos(sectorAngle / 2) + 20;

  // Glass INNER volume (truncated cone, accounting for wall and base thickness)
  const innerTopR = topRadius - wallThickness;
  const innerBotR = bottomRadius - wallThickness;
  const innerHeight = glassHeight - baseThickness;
  const volumeMm3 = (Math.PI * innerHeight / 3) * (innerTopR * innerTopR + innerBotR * innerBotR + innerTopR * innerBotR);
  const volumeMl = volumeMm3 / 1000;

  return {
    glassHeight,
    topRadius,
    bottomRadius,
    topCircumference,
    bottomCircumference,
    slantHeight,
    innerR,
    outerR,
    sectorAngle,
    sectorAngleDeg: (sectorAngle * 180) / Math.PI,
    svgWidth,
    svgHeight,
    D,
    volumeMl,
    wallThickness,
    baseThickness,
  };
}

/**
 * Compute the fill height (from bottom) for a given liquid volume.
 * Returns the height in mm and as a fraction of total glass height.
 */
function computeFillHeight(template, volumeMl) {
  const { glassHeight, topRadius, bottomRadius, volumeMl: totalVol, wallThickness, baseThickness } = template;
  if (volumeMl >= totalVol) return { heightMm: glassHeight, fraction: 1 };

  const innerTopR = topRadius - (wallThickness || 3);
  const innerBotR = bottomRadius - (wallThickness || 3);
  const innerH = glassHeight - (baseThickness || 5);
  const targetMm3 = volumeMl * 1000;

  // Binary search for fill height (measured from inside bottom)
  let lo = 0, hi = innerH;
  for (let i = 0; i < 50; i++) {
    const mid = (lo + hi) / 2;
    const rMid = innerBotR + (innerTopR - innerBotR) * mid / innerH;
    const vol = (Math.PI * mid / 3) * (innerBotR * innerBotR + rMid * rMid + innerBotR * rMid);
    if (vol < targetMm3) lo = mid; else hi = mid;
  }
  const fillH = (lo + hi) / 2;
  // Convert inner fill height to outer glass height fraction
  // fillH is from inner bottom; outer equivalent = baseThickness + fillH
  const outerFillH = (baseThickness || 5) + fillH;
  return { heightMm: outerFillH, fraction: outerFillH / glassHeight };
}

/**
 * Generate the SVG path for the glass wrap outline.
 * The shape is a sector of an annulus (fan/trapezoid with curved edges).
 *
 * @param {Object} template - From computeGlassTemplate
 * @returns {string} SVG path d attribute
 */
function glassWrapPath(template) {
  const { innerR, outerR, sectorAngle } = template;
  const halfAngle = sectorAngle / 2;

  // Center the sector with apex at origin, opening upward
  // Points on the arcs:
  // Bottom-left (inner arc, left)
  const blx = -innerR * Math.sin(halfAngle);
  const bly = -innerR * Math.cos(halfAngle);
  // Bottom-right (inner arc, right)
  const brx = innerR * Math.sin(halfAngle);
  const bry = -innerR * Math.cos(halfAngle);
  // Top-left (outer arc, left)
  const tlx = -outerR * Math.sin(halfAngle);
  const tly = -outerR * Math.cos(halfAngle);
  // Top-right (outer arc, right)
  const trx = outerR * Math.sin(halfAngle);
  const try_ = -outerR * Math.cos(halfAngle);

  // SVG arc: A rx ry x-rotation large-arc-flag sweep-flag x y
  const largeArc = sectorAngle > Math.PI ? 1 : 0;

  return [
    `M ${tlx.toFixed(2)} ${tly.toFixed(2)}`, // top-left
    `A ${outerR.toFixed(2)} ${outerR.toFixed(2)} 0 ${largeArc} 1 ${trx.toFixed(2)} ${try_.toFixed(2)}`, // top arc (outer)
    `L ${brx.toFixed(2)} ${bry.toFixed(2)}`, // right edge
    `A ${innerR.toFixed(2)} ${innerR.toFixed(2)} 0 ${largeArc} 0 ${blx.toFixed(2)} ${bly.toFixed(2)}`, // bottom arc (inner)
    `Z`, // close
  ].join(" ");
}

/**
 * Create a warp function that maps rectangular (x, y) coordinates
 * to the curved glass wrap space.
 *
 * Input rectangle: (0, 0) to (rectWidth, rectHeight)
 *   - x=0 is left edge, x=rectWidth is right edge
 *   - y=0 is top (lip of glass), y=rectHeight is bottom
 *
 * @param {Object} template - From computeGlassTemplate
 * @param {number} rectWidth - Width of the rectangular canvas
 * @param {number} rectHeight - Height of the rectangular canvas
 * @returns {Function} (x, y) => [wx, wy] in glass wrap space
 */
function createWarpFunction(template, rectWidth, rectHeight) {
  const { innerR, outerR, sectorAngle } = template;
  const halfAngle = sectorAngle / 2;

  return function warp(x, y) {
    // Normalize to [0, 1]
    const nx = x / rectWidth;   // 0 = left, 1 = right
    const ny = y / rectHeight;  // 0 = top (lip), 1 = bottom

    // Map y to radius: top (ny=0) -> outerR, bottom (ny=1) -> innerR
    const r = outerR - ny * (outerR - innerR);

    // Map x to angle: left (nx=0) -> -halfAngle, right (nx=1) -> +halfAngle
    const angle = -halfAngle + nx * sectorAngle;

    // Convert polar to cartesian (apex at origin, opening downward in SVG)
    const wx = r * Math.sin(angle);
    const wy = -r * Math.cos(angle);

    return [wx, wy];
  };
}

/**
 * Warp an array of [x, y] coordinates from rectangular to glass space.
 */
function warpCoords(coords, warpFn) {
  return coords.map(([x, y]) => warpFn(x, y));
}

/**
 * Warp an entire layout (from computeLayout) to glass space.
 * Maps from the actual content bounding box (not full canvas) to fill the glass.
 */
/**
 * @param {Object} layout
 * @param {Object} template
 * @param {Object} paddingOpts - { topPadding: 0-1, bottomPadding: 0-1 } fraction of glass height
 */
function warpLayout(layout, template, paddingOpts) {
  const topPad = paddingOpts?.topPadding || 0;
  const botPad = paddingOpts?.bottomPadding || 0;
  // Find the bounding box of visible content (features + hole labels)
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const hole of layout.holes) {
    // Include tee position + label space (circle + text ≈ 20px below tee)
    minX = Math.min(minX, hole.startX - 16);
    maxX = Math.max(maxX, hole.startX + 16);
    minY = Math.min(minY, hole.startY - 6);
    maxY = Math.max(maxY, hole.startY + 20);
    for (const f of hole.features) {
      for (const [x, y] of f.coords) {
        minX = Math.min(minX, x);
        maxX = Math.max(maxX, x);
        minY = Math.min(minY, y);
        maxY = Math.max(maxY, y);
      }
    }
  }

  // Padding to ensure nothing clips the glass edges
  const pad = 12;
  minX -= pad; minY -= pad; maxX += pad; maxY += pad;
  const contentW = maxX - minX;
  const contentH = maxY - minY;

  // Reserve left edge for text (6% of width)
  const textReserve = 0.06;
  const { innerR, outerR, sectorAngle } = template;
  const halfAngle = sectorAngle / 2;

  // Warp from content bbox to glass sector
  // topPad/botPad push content inward from the glass edges (as fraction of radial span)
  // edgeInset adds a small safety margin on top
  const edgeInset = 0.03;
  const rTop = outerR - (outerR - innerR) * (edgeInset + topPad);
  const rBot = innerR + (outerR - innerR) * (edgeInset + botPad);

  function warpPt(x, y) {
    const nx = textReserve + ((x - minX) / contentW) * (1 - textReserve - 0.02);
    const ny = (y - minY) / contentH;
    const r = rTop - ny * (rTop - rBot);
    const angle = -halfAngle + nx * sectorAngle;
    return [r * Math.sin(angle), -r * Math.cos(angle)];
  }

  const warpedHoles = layout.holes.map((hole) => {
    const [sx, sy] = warpPt(hole.startX, hole.startY);
    const [ex, ey] = warpPt(hole.endX, hole.endY);
    return {
      ...hole,
      startX: sx, startY: sy, endX: ex, endY: ey,
      direction: hole.direction,
      features: hole.features.map((f) => ({
        ...f,
        coords: f.coords.map(([x, y]) => warpPt(x, y)),
      })),
    };
  });

  // Enforce minimum slope after warp (warp can compress vertical separation)
  if (typeof enforceSlope === "function") enforceSlope(warpedHoles);

  return {
    ...layout,
    holes: warpedHoles,
    warped: true,
    template,
  };
}
