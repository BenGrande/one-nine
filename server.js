const express = require("express");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = 3000;
const API_KEY = "M6WETXKESG6OWDDVAHFMDPROL4";
const API_BASE = "https://api.golfcourseapi.com/v1";

const OVERPASS_ENDPOINTS = [
  "https://overpass.kumi.systems/api/interpreter",
  "https://overpass-api.de/api/interpreter",
];

// ---- File-based cache ----
const CACHE_DIR = path.join(__dirname, "cache");
const SEARCH_CACHE_DIR = path.join(CACHE_DIR, "searches");
const MAP_CACHE_DIR = path.join(CACHE_DIR, "maps");
const SEARCH_TTL = 1000 * 60 * 60 * 24 * 7; // 7 days
const MAP_TTL = 1000 * 60 * 60 * 24 * 30; // 30 days (OSM data changes infrequently)

for (const dir of [CACHE_DIR, SEARCH_CACHE_DIR, MAP_CACHE_DIR]) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function safeCacheKey(str) {
  return str.replace(/[^a-zA-Z0-9._-]/g, "_");
}

function readCache(filePath, ttl) {
  try {
    if (!fs.existsSync(filePath)) return null;
    const stat = fs.statSync(filePath);
    if (Date.now() - stat.mtimeMs > ttl) return null;
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch {
    return null;
  }
}

function writeCache(filePath, data) {
  try {
    const json = JSON.stringify(data);
    fs.writeFileSync(filePath, json);
    console.log(`Cache written: ${filePath} (${(json.length / 1024).toFixed(1)}KB)`);
  } catch (err) {
    console.error("Cache write failed:", filePath, err.message);
  }
}

// ---- Static files ----
app.use(express.static(path.join(__dirname, "public")));

// ---- Search endpoint ----
app.get("/api/search", async (req, res) => {
  const query = req.query.q;
  if (!query || query.trim().length === 0) {
    return res.json({ courses: [] });
  }

  const normalized = query.trim().toLowerCase();
  const cacheFile = path.join(SEARCH_CACHE_DIR, safeCacheKey(normalized) + ".json");

  const cached = readCache(cacheFile, SEARCH_TTL);
  if (cached) {
    console.log(`Search cache hit: "${normalized}"`);
    return res.json(cached);
  }

  try {
    const url = `${API_BASE}/search?search_query=${encodeURIComponent(query)}`;
    const response = await fetch(url, {
      headers: { Authorization: `Key ${API_KEY}` },
    });

    if (!response.ok) {
      return res
        .status(response.status)
        .json({ error: `API returned ${response.status}` });
    }

    const data = await response.json();
    writeCache(cacheFile, data);
    console.log(`Search cached: "${normalized}" (${data.courses?.length || 0} courses)`);
    res.json(data);
  } catch (err) {
    console.error("API error:", err);
    res.status(500).json({ error: "Failed to fetch from golf course API" });
  }
});

// ---- Overpass query with retry/fallback ----
async function queryOverpass(query) {
  for (let i = 0; i < OVERPASS_ENDPOINTS.length; i++) {
    const endpoint = OVERPASS_ENDPOINTS[i];
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: `data=${encodeURIComponent(query)}`,
          signal: AbortSignal.timeout(60000),
        });

        if (response.status === 429 || response.status === 504) {
          if (attempt === 0) {
            await new Promise((r) => setTimeout(r, 2000));
            continue;
          }
          break;
        }

        if (!response.ok) {
          break;
        }

        const text = await response.text();
        if (text.trimStart().startsWith("<")) {
          console.warn(`Overpass ${endpoint} returned HTML (busy), trying next...`);
          break;
        }

        return JSON.parse(text);
      } catch (err) {
        console.warn(`Overpass ${endpoint} attempt ${attempt + 1} failed:`, err.message);
        if (attempt === 0) continue;
        break;
      }
    }
  }
  return null;
}

function parseOverpassFeatures(raw) {
  const nodes = {};
  for (const el of raw.elements) {
    if (el.type === "node") {
      nodes[el.id] = [el.lat, el.lon];
    }
  }

  const features = [];
  for (const el of raw.elements) {
    if (el.type !== "way" || !el.tags) continue;

    const coords = (el.nodes || [])
      .map((id) => nodes[id])
      .filter(Boolean);
    if (coords.length < 2) continue;

    const golfType = el.tags.golf || null;
    const leisure = el.tags.leisure || null;
    const natural = el.tags.natural || null;
    const water = el.tags.water || null;

    let category;
    if (golfType === "fairway") category = "fairway";
    else if (golfType === "green") category = "green";
    else if (golfType === "tee") category = "tee";
    else if (golfType === "bunker") category = "bunker";
    else if (golfType === "rough") category = "rough";
    else if (golfType === "hole") category = "hole";
    else if (golfType === "cartpath" || golfType === "path") category = "path";
    else if (golfType === "driving_range") category = "fairway";
    else if (natural === "water" || water) category = "water";
    else if (leisure === "golf_course") category = "course_boundary";
    else continue;

    features.push({
      id: el.id,
      category,
      ref: el.tags.ref || null,
      par: el.tags.par ? Number(el.tags.par) : null,
      name: el.tags.name || null,
      coords,
    });
  }

  return features;
}

// ---- Course map endpoint ----
app.get("/api/course-map", async (req, res) => {
  const { lat, lng, radius } = req.query;
  if (!lat || !lng) {
    return res.status(400).json({ error: "lat and lng required" });
  }

  const r = Math.min(Number(radius) || 2000, 3000);
  const cacheFile = path.join(MAP_CACHE_DIR, safeCacheKey(`${lat}_${lng}_${r}`) + ".json");

  const cached = readCache(cacheFile, MAP_TTL);
  if (cached) {
    console.log(`Map cache hit: (${lat}, ${lng})`);
    return res.json(cached);
  }

  const query = `[out:json][timeout:60];
(
  way["golf"](around:${r},${lat},${lng});
  way["natural"="water"](around:${r},${lat},${lng});
  way["water"](around:${r},${lat},${lng});
  way["leisure"="golf_course"](around:${r},${lat},${lng});
  relation["leisure"="golf_course"](around:${r},${lat},${lng});
);
out body;>;out skel qt;`;

  try {
    const raw = await queryOverpass(query);

    if (!raw) {
      return res
        .status(503)
        .json({ error: "Overpass servers are busy. Please try again." });
    }

    console.log(`Overpass returned ${raw.elements?.length || 0} elements for (${lat}, ${lng})`);

    const features = parseOverpassFeatures(raw);
    const result = { features, center: [Number(lat), Number(lng)] };

    // Only cache if we got meaningful data (avoid caching empty results from partial failures)
    if (features.length > 0) {
      writeCache(cacheFile, result);
      console.log(`Map cached: (${lat}, ${lng}) — ${features.length} features`);
    }

    res.json(result);
  } catch (err) {
    console.error("Overpass error:", err);
    res.status(500).json({ error: "Failed to fetch course map data" });
  }
});

app.listen(PORT, () => {
  console.log(`Golf Maps running at http://localhost:${PORT}`);
  console.log(`Cache directory: ${CACHE_DIR}`);
});
