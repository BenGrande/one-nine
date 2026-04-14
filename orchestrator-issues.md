# Orchestrator Post-Mortem: Why 4 Rounds of Plans Didn't Fix the Issues

**Date**: 2026-04-14
**Context**: 4 plans were written to the orchestrator inbox on 2026-04-13. The orchestrator broke them into 27 API tasks + 12 frontend tasks, all executed and marked "done" in the outboxes. Yet the user reported the same issues across 4 consecutive rounds of screenshots.

---

## Diagnosis: Where Things Went Wrong

### The Timeline

The orchestrator received 4 plans and broke them into **27 API tasks + 12 frontend tasks**, all executed and marked "done" in the outboxes. Yet the user reported the same issues across 4 consecutive rounds. Here's where the blame falls:

---

## 1. Plan Quality (Plan Author) — ~20% of the problem

### What was wrong:

- **Glass ruler coordinate math was underspecified.** The plans described the *visual design* clearly (alternating rectangles, dual-side ticks, hole numbers on left) but never specified the **polar coordinate transformation math** needed for glass mode. The backend agent had to figure out how to place rectangles in a sector, and got it wrong every time. The critical detail — that elements at positive x in the rotated frame are *outside* the glass sector — was never stated.

- **Terrain-following zone algorithm was hand-wavy.** Plans said "offset contours" and "elliptical offsets" without providing concrete math. The backend agent implemented something that produced degenerate polygons (the "weird horizontal lines" and concentric green shapes visible in screenshots).

- **The architectural root cause (diverged pipelines) wasn't identified until Round 4.** The first 3 plans all said "fix cricut export" without recognizing that the export (`cricut.py`) was a completely separate codebase from the preview (`svg.py`). This should have been caught in Round 1 by reading `cricut.py` more carefully.

### What was right:

- Issue identification was thorough — every user complaint was captured
- Visual specifications (ASCII diagrams, alternating rectangle design) were clear
- File/line references were accurate
- Dependency ordering was correct
- Verification checklists were comprehensive (Round 3 and Round 4 plans had 24+ item checklists)

---

## 2. Orchestrator (Delegation Agent) — ~15% of the problem

### What the orchestrator got wrong:

- **Marked tasks "done" without visual verification.** All 27 API tasks and 12 frontend tasks have "done" files in the outbox, yet the user saw broken output in every round. The orchestrator accepted the agents' word that tasks were complete without checking rendered SVG output.

- **Didn't enforce dependencies properly.** Tasks like "fix cricut export" (Task 023) were completed before the architectural prerequisite (Task 024 "unify pipelines") existed. The orchestrator should have recognized that fixing cricut separately was futile when the root cause was diverged codebases.

- **Didn't catch regressions across rounds.** When Round 3 re-reported issues from Round 2 (ruler broken, export broken, no course name), the orchestrator should have flagged that previous "done" tasks had regressed or were never actually working.

### What the orchestrator got right:

- Task breakdown was reasonable — each plan was split into focused tasks
- Task numbering and ordering generally respected dependencies
- Both API and frontend agents received appropriate tasks

---

## 3. Backend Agent — ~55% of the problem (primary culprit)

This is where most failures occurred. The backend agent repeatedly:

### A. Implemented features that "look right in code" but don't render correctly

- **Glass ruler — broken in ALL 4 rounds.** The agent wrote `_render_ruler_warped()` that placed score elements at positive x (outside the glass sector). The code *looks* plausible — it uses rotation transforms, it computes polar coordinates — but the sign of `score_cx` was wrong. A simple test rendering would have caught this.

- **Terrain zone contours produced artifacts.** The `compute_terrain_following_zones()` function generates polygon offsets, but the resulting polygons create visual garbage (horizontal lines, concentric shapes around greens). The agent didn't render the output to check.

- **Stats box positioning overlapped fairway.** The agent placed stats at canvas margins (`draw_left`/`draw_right`) instead of relative to the hole number circle. The fix was to position them on the opposite side of the hole number from the fairway direction.

### B. Didn't actually unify the rendering pipelines when told to

- Task 024 "Unify Preview and Export" was marked "done" in the outbox, but `cricut.py` still had its own separate rendering — `render_cricut_white()` was still a standalone ~200-line function, not calling `_render_vinyl_preview()`. The agent likely added the `layer` parameter to `_render_vinyl_preview()` but never rewired `cricut.py` to use it.

### C. Didn't pass data through the full pipeline

- `hole_range` was never passed from the `render.py` API endpoint to the SVG renderer options. The frontend sent it correctly, but the backend discarded it. The API was copying `course_name` from the request body to options but not `hole_range`.

### D. Stroke widths weren't actually reduced when requested

- Plans said "reduce from 0.8 to 0.4" and the agent may have changed values in one code path, but the user reported "still too thick" in rounds 3 and 4. Either the values weren't changed in the vinyl preview mode where they matter, or they were changed in a path that doesn't execute.

---

## 4. Frontend Agent — ~10% of the problem

The frontend agent was mostly competent:

### What worked:
- URL persistence (`router.replace` with courseId/lat/lng) was correctly implemented
- Export download logic (blob creation, JSZip) was structurally sound
- Course name was properly sent in render requests
- `hole_range` computation was correctly implemented

### What didn't:
- The multi-glass cricut response handling may have been a bug (expecting flat `{white, green, ...}` when API returns `{glasses: [...]}` for multi-glass), though this is partially an API documentation issue.

---

## Summary Table

| Category | Blame % | Key Failures |
|----------|---------|-------------|
| **Plan quality** | ~20% | Glass ruler math underspecified; terrain zone algorithm vague; didn't identify diverged pipelines until Round 4 |
| **Orchestrator** | ~15% | No visual verification of "done" tasks; didn't catch regressions; didn't enforce task dependencies |
| **Backend agent** | ~55% | Glass ruler wrong in every round; didn't actually unify pipelines; stats positioned wrong; didn't pass hole_range; never rendered output to verify |
| **Frontend agent** | ~10% | Multi-glass response handling; otherwise solid |

---

## Root Causes (Systemic)

### 1. No visual testing in the loop
Nobody rendered an SVG and looked at it. The backend agent checked code logic but never produced actual output. Every user complaint would have been caught by opening the SVG in a browser.

### 2. "Done" doesn't mean "works"
The outbox has 39 "done" files, but the user saw broken output in every round. There's no verification step between "code written" and "task closed."

### 3. The glass sector coordinate system was never documented
Every time someone touches the glass ruler, they have to reverse-engineer the polar transformation. A single diagram showing the sector coordinate system (what's positive x, what's negative, where the glass edge is) would prevent the recurring ruler bugs.

### 4. Separate pipelines are a design flaw, not a feature
Having `cricut.py` and `svg.py` render the same content independently guarantees drift. The correct fix (making cricut call the shared `_render_vinyl_preview()` function with a layer parameter) should have been the architecture from the start.

---

## Recommendations

### For Plans
1. When specifying coordinate transformations, include the actual math — not just "rotate elements to follow curvature"
2. When an algorithm is non-trivial (like polygon offset for terrain zones), provide pseudocode, not just a description
3. Identify architectural issues (like diverged pipelines) early by reading ALL relevant files, not just the one being fixed

### For the Orchestrator
1. **Require visual verification** — before marking any rendering task "done", the agent must render a real course SVG and confirm it visually matches the specification
2. **Check for regressions** — if a task in Round N addresses the same issue as a "done" task from Round N-1, flag it and investigate why it regressed
3. **Enforce dependency order** — don't let a task complete if its prerequisite isn't truly done
4. **Include a "smoke test" step** — render one SVG, open it, check for obvious issues (clipping, overlapping, missing elements)

### For the Backend Agent
1. **Always render output and inspect it** — never ship rendering code without looking at what it produces
2. **Test both rect AND glass modes** — glass mode has entirely different coordinate math and breaks independently
3. **When told to "unify" code, verify the old path is actually removed** — adding a layer parameter is useless if the old separate function is still being called
4. **Trace data flow end-to-end** — when a value (like hole_range) should appear in the output, verify it flows from frontend POST body → API endpoint → renderer options → SVG output

### For the Frontend Agent
1. Handle both response shapes from multi-glass APIs (`{white, green, ...}` vs `{glasses: [...]}`)
2. Surface API errors to the user instead of silently falling back to empty content
