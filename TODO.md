# TODO

## Beer Level / Score Zone Alignment

The 3D beer level doesn't accurately match the ruler markings on the glass. Additionally, the score options in the ScoreCard modal may not align with the scoring zones available on the glass wrap.

**Issues:**
- Beer level in the 3D glass view doesn't precisely match the corresponding score position on the ruler
- Some scoring zones get merged on the backend (e.g., +0, +1, +2 disappear on holes with tight spacing), but the ScoreCard still offers those scores — the beer level computation has to interpolate, which may not match the ruler visually
- The zone height fractions are computed from flat layout coordinates (pre-warp), while the 3D texture uses the warped sector SVG — these coordinate spaces may not map 1:1

**Files involved:**
- `api/app/services/render/scoring.py` — zone computation and merging logic
- `frontend/src/composables/useGlassBeerLevel.ts` — beer height from scores/zones
- `frontend/src/composables/useGlassScene.ts` — `buildBeerGeometry()` height mapping
- `api/app/api/v1/games.py` — `glass-3d` endpoint zone fraction computation
