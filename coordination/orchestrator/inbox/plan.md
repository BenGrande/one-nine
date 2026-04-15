# Split the Tee — Golf Drinking Game Glass System

## Vision

A configurable set of pint glasses (default: 3 glasses, 6 holes each, 18 total) where the beer level IS the golf shot. Players drink and score based on where the liquid line falls relative to each hole's green. The number of glasses and holes per glass are configurable in the designer. The glasses are produced with Cricut-cut vinyl in 3 colors (white, green, tan) on clear glass — minimalist, high-end, and functional.

---

## Gameplay

### How It Works
1. Fill glass to the brim. Hole 1 is at the top (lip), last hole is near the base.
2. Players take turns sipping. After each sip, check where the beer level sits relative to the current hole's green.
3. Score the hole using the concentric scoring zones around the green.
4. Progress downward through all holes on the glass, then move to the next glass.
5. After all glasses (configurable: default 3 glasses x 6 holes = 18 holes), lowest cumulative score wins.

### Scoring Zones (per hole, vertical bands)
Each hole has concentric horizontal scoring zones that get **narrower closer to the green** (higher precision required for better scores):

```
 ── +5 zone ──  (widest, furthest above green — toward lip)
 ── +4 zone ──
 ── +3 zone ──
 ── +2 zone ──  (narrowing)
 ── +1 zone ──  (narrow)
 ──  0 zone ──  (thin band just outside the green)
 ┌─ GREEN ─────┐
 │   -1 (small │  ← beer visible through bare glass
 │    greens)  │
 │ or -1 near  │  ← for larger greens: -1 near hole, 0 outer region
 │    hole, 0  │
 │   outer     │
 └─────────────┘
 ── +1 zone ──  (small buffer below green, room permitting)
 ── +2 zone ──  (can slightly overlap next tee box vertical space)
 ─── next tee ──
```

- Zones **above** the green go up to +5 (toward lip).
- A small number of zones **below** the green (+1, +2) provide buffer before the next hole's tee box. These can slightly encroach on the next hole's vertical space but not far.
- If a player overshoots and lands on the **next hole**, automatic **+5 or +8** penalty.
- **Smaller greens**: entire green interior = -1.
- **Larger greens**: small inner region near an arbitrary hole location = -1, outer region of green = 0.

### Ruler (right side of glass)
A vertical ruler on the far right edge (opposite the course name) with:
- Tick marks for each scoring zone boundary per hole
- Score labels (-1, 0, 1, 2, 3, 4, 5) at each tick
- Hole number labels (1, 2, 3...)
- Makes it easy to resolve disputes — hold glass up, read the ruler

---

## Visual Design

### Color Palette (3 vinyl colors + bare glass)
| Color | Vinyl | Used For |
|-------|-------|----------|
| **White** | White vinyl | Outlines, labels, ruler, scoring zone arcs, hole numbers, stats text, brand name, QR code |
| **Green** | Green vinyl | Green outlines (interior cut out for beer visibility), tee box shapes, fairway accent outlines |
| **Tan** | Tan vinyl | Bunker shapes |
| **Clear** | No vinyl (bare glass) | Green interiors (beer shows through), spacing between elements, majority of glass surface |

### Layout (per glass, top to bottom)

The glass has three vertical bands: left text strip, center course area, right ruler.

```
┌────────────────────────────────────────────────────────────┐
│ LIP OF GLASS                                                │
│                                                              │
│ ┌──────┐                                        ┌─────────┐ │
│ │      │  ┌─ HOLE 1 ──────────────────────┐     │ 5 4 3 2 │ │
│ │  C   │  │  +5 +4 +3 +2 +1 0  ← arcs    │     │ 1 0 -1  │ │
│ │  O   │  │  [TEE - green]  Par 4 345yd   │     │─────────│ │
│ │  U   │  │  ~fairway~ ~~bunkers~~        │     │ 5 4 3 2 │ │
│ │  R   │  │  [GREEN - hollow cutout]      │     │ 1 0 -1  │ │
│ │  S   │  │  +1 +2 buffer                 │     │─────────│ │
│ │  E   │  └───────────────────────────────┘     │         │ │
│ │      │                                        │ 5 4 3 2 │ │
│ │  N   │  ┌─ HOLE 2 ──────────────────────┐     │ 1 0 -1  │ │
│ │  A   │  │  ...same structure...          │     │─────────│ │
│ │  M   │  └───────────────────────────────┘     │         │ │
│ │  E   │                                        │ ...     │ │
│ │      │  ... holes 3-5 ...                      │         │ │
│ │ ──── │                                        │         │ │
│ │Holes │  ┌─ HOLE 6 ──────────────────────┐     │ 5 4 3 2 │ │
│ │ 1-6  │  │  ...same structure...          │     │ 1 0 -1  │ │
│ └──────┘  └───────────────────────────────┘     └─────────┘ │
│                                                              │
│  [one nine logo]  [QR Code]        ← bottom-left, small     │
│ BASE OF GLASS                                                │
└────────────────────────────────────────────────────────────┘
```

#### Left Text Strip
- **Course name** runs vertically, reading bottom-to-top (first letter at bottom, last letter at top).
- **Font**: Intelligently sourced from the course's website if available. Fallback to a specified all-caps display font (TBD).
- **Hole range** (e.g., "Holes 1–6") displayed below the course name on the same vertical strip, also reading bottom-to-top.
- White vinyl only.

#### Center Course Area
- Holes flow top-to-bottom with tee at top, green at bottom per hole.
- Scoring zone arcs surround each green (white vinyl).
- Course features: green outlines (green vinyl, hollow interior), tee boxes (green vinyl), fairway accents (green vinyl), bunkers (tan vinyl).
- Hole stats (par, yardage, handicap) in white, positioned in empty space near each hole.

#### Right Ruler
- Vertical ruler with tick marks and score labels per hole.
- Each hole's scoring zones mirrored as horizontal ticks with labels (-1, 0, 1, 2, 3, 4, 5).
- Hole number labels at each section.
- White vinyl only.

#### Bottom Strip
- **Split the Tee logo** — small, bottom-left near the glass base. This is the only location the logo appears.
- **QR code** — next to logo, links to score-keeping app.

### Vinyl Production Workflow (Cricut)
1. **White sheet**: Cricut cuts the full layout — all outlines, scoring arcs, ruler, labels, hole numbers, stats, brand, QR code. One continuous piece applied to transfer tape.
2. **Green sheet**: Compact arrangement of all green/tee shapes (outlines only — interiors hollow). Cut, then manually place onto transfer tape in correct positions.
3. **Tan sheet**: Compact arrangement of all bunker shapes. Cut, then manually place onto transfer tape in correct positions.
4. **Apply**: Transfer the assembled vinyl from tape to glass.

### Design Principles
- **Minimalist**: Lots of bare glass visible. Elements don't feel crowded.
- **High-end**: Clean lines, consistent spacing, premium feel.
- **Functional**: Scoring zones are immediately readable. Ruler resolves disputes.
- **Flow is obvious**: Clear visual progression from tee to green on each hole, and from hole to hole down the glass.

### Hole Stats
Displayed in white, positioned intelligently in empty space near each hole:
- Par
- Yardage
- Handicap
- (Future: AI-generated fun facts)

---

## Score-Keeping Web App

### QR Code System
- Each **set of glasses** gets a unique QR code printed on each glass.
- The QR code URL encodes: glass set ID (acts as session/room code) + course ID + glass number.
- Scanning any glass's QR code opens the score-keeping webapp and auto-joins the room — no session code needed, the QR IS the session.
- All players scanning glasses from the same set are in the same game.

### App Features (MVP)
- **Room/session**: Automatically created from the QR glass set ID. No manual codes.
- **Player registration**: Simple name entry on first scan.
- **Score entry**: Per-hole score input (-1 through +5/+8). Select current hole, tap score.
- **Leaderboard**: Live cumulative scores across all glasses. Lowest wins.
- **Course awareness**: Knows the course being played — displays real par, yardage, handicap per hole.
- **Cumulative tracking**: Scores persist across all glasses for the full round.

### App Features (Future)
- Real handicap calculations
- Game history / stats over time
- Multiple game modes
- Social sharing

---

## Tech Stack (Full Migration)

### Backend: FastAPI (Python)
Replaces the current Express/Node server entirely.

#### API Modules
| Module | Responsibility |
|--------|---------------|
| `api/search.py` | Golf course search (proxy to Golf Course API) |
| `api/osm.py` | Overpass/OSM queries with retry + caching |
| `api/holes.py` | Hole association, feature bundling |
| `api/layout.py` | Layout engine (port from JS), scoring zone computation |
| `api/render.py` | SVG rendering (port from JS) — rect, glass, and **Cricut export** modes |
| `api/settings.py` | Save/load glass design settings |
| `api/games.py` | Game sessions, rooms, score tracking |
| `api/qr.py` | QR code generation per glass set |

#### Data Models (MongoDB Collections)
```
courses        — cached course data from Golf Course API + OSM features
search_cache   — search query results with TTL
map_cache      — OSM map data with TTL
bundle_cache   — per-course hole bundles with TTL
glass_sets     — { _id, course_id, glass_count, holes_per_glass, course_name, created_at, qr_codes[] }
game_sessions  — { _id, glass_set_id, created_at, status, course_config }
players        — { _id, session_id, name, joined_at }
scores         — { _id, session_id, player_id, hole_number, glass_number, score, timestamp }
settings       — saved glass design configurations
```

#### Storage
- **MongoDB Atlas** (`terraport.k8cbg.mongodb.net`, database: `splitthetee`) for all data:
  - Course/search/map caching (with TTL indexes replacing file-based cache)
  - Game sessions, players, scores
  - Glass set configurations and design settings
- Connection string managed via `.env` (same cluster as ion/llc projects)

### Frontend: Vue 3 + Vite + Tailwind CSS

#### Apps / Views
| View | Purpose |
|------|---------|
| **Admin/Designer** | Current functionality — search courses, preview glass layouts, configure styles, export SVGs. Configurable glass count + holes per glass. Enhanced with scoring zone preview and Cricut export. |
| **Score App** | Mobile-first. Opened via QR code. Join room, enter scores, view leaderboard. |
| **Customer Frontend** (future) | Course search → glass preview → order button. Separate build. |

### New SVG Rendering Modes

#### Current
- `rect` — flat rectangular layout
- `glass` — warped to pint glass shape

#### New
- `cricut-white` — white layer only: outlines, labels, ruler, scoring arcs, stats, QR code, brand. Single continuous cut path.
- `cricut-green` — green pieces only: green outlines (hollow), tee boxes, fairway accents. Compact arrangement for efficient cutting.
- `cricut-tan` — tan pieces only: bunker shapes. Compact arrangement.
- `scoring-preview` — full layout with scoring zones visualized (colored bands) for testing/admin.

---

## Implementation Phases

### Phase 1: FastAPI + Vue/Vite Migration
1. Set up FastAPI project structure (`api/`) with motor (async MongoDB driver)
2. Set up Vue 3 + Vite + Tailwind frontend (`frontend/`)
3. MongoDB connection to Atlas cluster (`splitthetee` database), TTL indexes for caching
4. Port search, OSM, hole association from Node to Python (store in MongoDB instead of file cache)
5. Port layout engine and SVG renderer to Python
6. Port full designer UI to Vue (same controls: glass count, holes per glass, glass dimensions, styles, layers, fonts, logo, save/load, export)
7. Make glass count + holes per glass configurable (already partially exists, make it first-class)
8. Verify parity with current Node app, then cut over

### Phase 2: Scoring Zones + Ruler
1. Scoring zone computation in layout engine (zone heights narrow toward green)
2. Concentric arc rendering around each green in SVG
3. Ruler generation on right edge (tick marks + score labels per hole)
4. Hole stats display (par, yardage, handicap) positioned in empty space near each hole
5. Scoring preview mode in designer (visualize zones with colored bands)

### Phase 3: Cricut Export
1. Implement 3-color SVG export (white, green, tan as separate SVGs)
2. Green layer: green outlines with hollow interiors, tee boxes, fairway accents
3. White layer: all labels, scoring arcs, ruler, outlines, brand, QR code
4. Tan layer: bunker shapes
5. Compact layout mode for green/tan sheets (arrange pieces efficiently for cutting)
6. Print test page with 1:1 scale ruler verification

### Phase 4: Score-Keeping App
1. MongoDB models for glass sets, sessions, players, scores
2. QR code generation (unique per glass set, encodes set ID + course + glass number)
3. Game session API (create room via QR scan, join, submit scores, leaderboard)
4. Vue score-keeping UI (mobile-first, opened via QR scan)
5. Live leaderboard with cumulative scores across all glasses

### Phase 5: Polish
1. Brand integration (Split the Tee logo on glass + app)
2. Fine-tune scoring zone widths per hole (based on green size, par, difficulty)
3. Admin UI for previewing scoring zones and adjusting
4. Customer-facing frontend (future)

---

## Open Questions / Future Decisions
- Exact scoring zone height ratios (narrowing curve toward green) — to be tuned per-course
- Overshoot penalty: +5 or +8? (configurable?)
- Should larger greens have a visible "hole" marker for the -1 zone, or just a designated region?
- Glass dimensions will be standardized later — current default is 16oz pint (146mm H, 43mm top R, 30mm bottom R)
- AI-generated fun facts for holes — future feature, placeholder space reserved
