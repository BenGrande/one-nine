// SVG Renderer: produces SVG from layout data

var DEFAULT_STYLES = {
  course_boundary: { fill: "#3d6b3d", stroke: "#2d5a2d", strokeWidth: 0.5, opacity: 0.2 },
  rough:           { fill: "#8ab878", stroke: "none", strokeWidth: 0, opacity: 0.5 },
  fairway:         { fill: "#4a8f3f", stroke: "#3d7a34", strokeWidth: 0.3, opacity: 0.85 },
  bunker:          { fill: "#e8dca0", stroke: "#d4c87a", strokeWidth: 0.3, opacity: 0.9 },
  water:           { fill: "#5b9bd5", stroke: "#4a87be", strokeWidth: 0.3, opacity: 0.85 },
  tee:             { fill: "#7bc96a", stroke: "#5eaa50", strokeWidth: 0.3, opacity: 0.9 },
  green:           { fill: "#5cc654", stroke: "#3eaa36", strokeWidth: 0.5, opacity: 0.95 },
  hole_number:     { fill: "rgba(0,0,0,0.65)", stroke: "#ffffff", strokeWidth: 0.4, opacity: 1 },
  hole_par:        { fill: "rgba(255,255,255,0.5)", stroke: "none", strokeWidth: 0, opacity: 1 },
  background:      { fill: "#1a472a" },
};

var ALL_LAYERS = [
  "background", "rough", "fairway", "water", "bunker", "tee", "green",
  "hole_number", "hole_par",
];

var FEATURE_LAYERS = ["rough", "water", "fairway", "bunker", "tee", "green"];

var LAYER_LABELS = {
  rough: "Rough", fairway: "Fairway", water: "Water", bunker: "Bunker",
  tee: "Tee Box", green: "Green",
  hole_number: "Hole Number", hole_par: "Par Label", background: "Background",
};

var HOLE_HUES = [120,150,90,180,60,200,100,160,75,130,170,80,190,55,210,110,145,85];
function holeHue(i) { return HOLE_HUES[i % HOLE_HUES.length]; }

function tintColor(hex, hue, amt) {
  if (!hex || hex === "none" || hex.startsWith("rgba")) return hex;
  const rgb = hexToRgb(hex); if (!rgb) return hex;
  const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
  const nh = hsl.h + (hue - hsl.h) * amt;
  const nr = hslToRgb(((nh%360)+360)%360, hsl.s, hsl.l);
  return `rgb(${nr.r},${nr.g},${nr.b})`;
}
function hexToRgb(h){h=h.replace("#","");if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];if(h.length!==6)return null;return{r:parseInt(h.slice(0,2),16),g:parseInt(h.slice(2,4),16),b:parseInt(h.slice(4,6),16)};}
function rgbToHsl(r,g,b){r/=255;g/=255;b/=255;const mx=Math.max(r,g,b),mn=Math.min(r,g,b);let h=0,s=0,l=(mx+mn)/2;if(mx!==mn){const d=mx-mn;s=l>0.5?d/(2-mx-mn):d/(mx+mn);if(mx===r)h=((g-b)/d+(g<b?6:0))*60;else if(mx===g)h=((b-r)/d+2)*60;else h=((r-g)/d+4)*60;}return{h,s,l};}
function hslToRgb(h,s,l){h/=360;let r,g,b;if(s===0){r=g=b=l;}else{const f=(p,q,t)=>{if(t<0)t+=1;if(t>1)t-=1;if(t<1/6)return p+(q-p)*6*t;if(t<1/2)return q;if(t<2/3)return p+(q-p)*(2/3-t)*6;return p;};const q=l<0.5?l*(1+s):l+s-l*s;const p=2*l-q;r=f(p,q,h+1/3);g=f(p,q,h);b=f(p,q,h-1/3);}return{r:Math.round(r*255),g:Math.round(g*255),b:Math.round(b*255)};}

function renderSvg(layout, opts = {}) {
  const styles = {};
  for (const k of Object.keys(DEFAULT_STYLES)) styles[k] = { ...DEFAULT_STYLES[k], ...(opts.styles?.[k] || {}) };

  const hidden = opts.hiddenLayers || new Set();
  const perHoleColors = opts.perHoleColors !== false;
  const fontFamily = opts.fontFamily || "'Arial', sans-serif";
  const { holes } = layout;
  const isWarped = layout.warped && layout.template;

  let vbX, vbY, vbW, vbH;
  if (isWarped) {
    const t = layout.template, halfA = t.sectorAngle / 2, pad = 8;
    vbX = -t.outerR * Math.sin(halfA) - pad;
    vbY = -t.outerR - pad;
    vbW = 2 * t.outerR * Math.sin(halfA) + pad * 2;
    vbH = t.outerR - t.innerR * Math.cos(halfA) + pad * 2;
  } else { vbX = 0; vbY = 0; vbW = layout.canvasWidth; vbH = layout.canvasHeight; }

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="${ff(vbX)} ${ff(vbY)} ${ff(vbW)} ${ff(vbH)}" width="${Math.round(vbW)}" height="${Math.round(vbH)}">`;
  svg += `<defs>`;
  if (isWarped) {
    svg += `<clipPath id="glassClip"><path d="${glassWrapPath(layout.template)}"/></clipPath>`;
    svg += buildTextPaths(layout.template);
  }
  svg += `</defs>`;

  if (isWarped) {
    svg += `<g clip-path="url(#glassClip)">`;
    if (!hidden.has("background")) svg += `<path d="${glassWrapPath(layout.template)}" fill="${styles.background.fill}"/>`;
  } else {
    if (!hidden.has("background")) svg += `<rect x="0" y="0" width="${layout.canvasWidth}" height="${layout.canvasHeight}" fill="${styles.background.fill}" rx="4"/>`;
  }

  for (const layer of FEATURE_LAYERS) {
    if (hidden.has(layer)) continue;
    const s = styles[layer]; if (!s) continue;
    const tintable = layer==="fairway"||layer==="rough"||layer==="tee"||layer==="green";
    svg += `<g class="layer-${layer}">`;
    for (let hi = 0; hi < holes.length; hi++) {
      const hue = holeHue(hi);
      for (const feat of holes[hi].features) {
        if (feat.category !== layer) continue;
        const d = coordsToPath(feat.coords, layer !== "path"); if (!d) continue;
        let fill = s.fill, stroke = s.stroke;
        if (perHoleColors && tintable && fill !== "none") fill = tintColor(fill, hue, 0.35);
        if (perHoleColors && tintable && stroke && stroke !== "none") stroke = tintColor(stroke, hue, 0.25);
        svg += `<path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${s.strokeWidth}" opacity="${s.opacity}"/>`;
      }
    }
    svg += `</g>`;
  }

  if (!hidden.has("hole_number")) {
    const s = styles.hole_number;
    const sz = isWarped ? 5 : 6, cr = isWarped ? 5 : 6;
    svg += `<g class="layer-hole_number">`;
    for (const hole of holes) {
      const xOff = hole.direction > 0 ? -(cr + 3) : (cr + 3);
      const lx = hole.startX + xOff, ly = hole.startY + cr + 4;
      svg += `<circle cx="${ff(lx)}" cy="${ff(ly)}" r="${cr}" fill="${s.fill}" stroke="${s.stroke}" stroke-width="${s.strokeWidth}" opacity="${s.opacity}"/>`;
      svg += `<text x="${ff(lx)}" y="${ff(ly + sz * 0.38)}" text-anchor="middle" fill="white" font-size="${sz}" font-weight="700" font-family="${fontFamily}">${hole.ref}</text>`;
    }
    svg += `</g>`;
  }

  if (!hidden.has("hole_par")) {
    const s = styles.hole_par, sz = isWarped ? 5 : 6;
    svg += `<g class="layer-hole_par">`;
    for (const hole of holes) {
      if (!hole.par) continue;
      const dx = hole.endX-hole.startX, dy = hole.endY-hole.startY, len = Math.sqrt(dx*dx+dy*dy)||1;
      const px = -dy/len, py = dx/len, off = 8;
      const lx = hole.endX + px*off*(hole.direction>0?1:-1), ly = hole.endY + py*off*(hole.direction>0?1:-1);
      svg += `<text x="${ff(lx)}" y="${ff(ly+2)}" text-anchor="middle" fill="${s.fill}" font-size="${sz*0.75}" font-family="${fontFamily}" opacity="${s.opacity}">P${hole.par}</text>`;
    }
    svg += `</g>`;
  }

  if (isWarped) {
    svg += `</g>`;
    if (opts.showGlassOutline !== false) svg += `<path d="${glassWrapPath(layout.template)}" fill="none" stroke="#555" stroke-width="0.5" stroke-dasharray="3,2"/>`;
  }

  if (opts.courseName || opts.holeRange || opts.logoDataUrl) {
    svg += isWarped ? renderWarpedText(layout, opts, fontFamily) : renderRectText(layout, opts, fontFamily);
  }

  svg += `</svg>`;
  return svg;
}

function buildTextPaths(template) {
  const { innerR, outerR, sectorAngle } = template;
  const halfA = sectorAngle / 2;
  let svg = "";
  const offsets = [0.01, 0.021, 0.031];
  for (let i = 0; i < 3; i++) {
    const angle = -halfA + offsets[i];
    svg += `<path id="textArc${i+1}" d="M ${ff(innerR*Math.sin(angle))} ${ff(-innerR*Math.cos(angle))} L ${ff(outerR*Math.sin(angle))} ${ff(-outerR*Math.cos(angle))}" fill="none"/>`;
  }
  return svg;
}

function renderWarpedText(layout, opts, fontFamily) {
  let svg = "";
  const t = layout.template, halfA = t.sectorAngle / 2;

  if (opts.logoDataUrl) {
    const midR = (t.innerR + t.outerR) / 2;
    const edgeAngle = -halfA + 0.015;
    const cx = midR * Math.sin(edgeAngle), cy = -midR * Math.cos(edgeAngle);
    const slantLen = t.outerR - t.innerR;
    const imgH = slantLen * 0.5, imgW = imgH * 0.35;
    const edgeDeg = edgeAngle * 180 / Math.PI;
    svg += `<image href="${opts.logoDataUrl}" x="${ff(cx-imgW/2)}" y="${ff(cy-imgH/2)}" width="${ff(imgW)}" height="${ff(imgH)}" transform="rotate(${ff(edgeDeg)}, ${ff(cx)}, ${ff(cy)})" preserveAspectRatio="xMidYMid meet"/>`;
  } else if (opts.courseName) {
    svg += `<text fill="white" font-size="7" font-weight="700" font-family="${fontFamily}" opacity="0.85" text-anchor="middle"><textPath href="#textArc1" startOffset="50%">${escXml(opts.courseName)}</textPath></text>`;
  }
  if (opts.holeRange) {
    svg += `<text fill="white" font-size="4" font-family="${fontFamily}" opacity="0.6" text-anchor="middle"><textPath href="#textArc2" startOffset="50%">${escXml(opts.holeRange)}</textPath></text>`;
  }
  if (opts.holeYardages?.length) {
    svg += `<text fill="white" font-size="3" font-family="${fontFamily}" opacity="0.5" text-anchor="middle"><textPath href="#textArc3" startOffset="50%">${escXml(opts.holeYardages.join("  "))}</textPath></text>`;
  }
  return svg;
}

function renderRectText(layout, opts, fontFamily) {
  let svg = "";
  const yMid = layout.canvasHeight / 2;
  if (opts.logoDataUrl) {
    const imgW = 20, imgH = layout.canvasHeight * 0.45;
    svg += `<image href="${opts.logoDataUrl}" x="3" y="${ff(yMid-imgH/2)}" width="${ff(imgW)}" height="${ff(imgH)}" transform="rotate(-90, ${ff(3+imgW/2)}, ${ff(yMid)})" preserveAspectRatio="xMidYMid meet"/>`;
  } else if (opts.courseName) {
    svg += `<text transform="translate(10, ${ff(yMid)}) rotate(-90)" text-anchor="middle" fill="white" font-size="12" font-weight="700" font-family="${fontFamily}" opacity="0.85">${escXml(opts.courseName)}</text>`;
  }
  if (opts.holeRange) svg += `<text transform="translate(22, ${ff(yMid)}) rotate(-90)" text-anchor="middle" fill="white" font-size="7" font-family="${fontFamily}" opacity="0.6">${escXml(opts.holeRange)}</text>`;
  if (opts.holeYardages?.length) svg += `<text transform="translate(31, ${ff(yMid)}) rotate(-90)" text-anchor="middle" fill="white" font-size="5" font-family="${fontFamily}" opacity="0.45">${escXml(opts.holeYardages.join("  "))}</text>`;
  return svg;
}

function coordsToPath(coords, closed) {
  if (!coords || coords.length < 2) return "";
  let d = `M${ff(coords[0][0])},${ff(coords[0][1])}`;
  for (let i = 1; i < coords.length; i++) d += `L${ff(coords[i][0])},${ff(coords[i][1])}`;
  if (closed) d += "Z";
  return d;
}

function ff(n) { return n.toFixed(1); }
function escXml(s) { return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
