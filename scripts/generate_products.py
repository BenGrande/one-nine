"""Product-page generation pipeline.

Usage:
    uv run python scripts/generate_products.py           # full run
    uv run python scripts/generate_products.py --dry-run # manifest + JSON only
    uv run python scripts/generate_products.py --only pebble-beach-pebble-beach-ca
    uv run python scripts/generate_products.py --force   # ignore cache

Stages (each gracefully skips if its dependency is missing):
    1. load courses   — curated JSON (always) + Mongo `courses` (if URI set)
    2. glass-3d       — Python render pipeline -> public/products/<slug>/glass-3d.json
    3. playwright     — headless capture -> glass-front.png / transparent / etc.
                        Skipped if playwright is not installed.
    4. patio          — Pillow composite -> patio.jpg.
                        Skipped if Pillow is not installed.
    5. stats + AI     — compute stats, call Anthropic for description, sanitize.
                        AI step skipped without ANTHROPIC_API_KEY.
    6. manifest       — frontend/src/generated/products.json + per-slug JSON.
    7. sitemap+robots — frontend/public/sitemap.xml + robots.txt.
    8. gc             — remove public/products/<slug> dirs no longer in the manifest.

Writes a cache at scripts/cache.json keyed on slug -> {input_hash, generated_at}
so unchanged courses skip the expensive stages.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
API_ROOT = ROOT / "api"
FRONTEND_ROOT = ROOT / "frontend"
PUBLIC_ROOT = FRONTEND_ROOT / "public"
GENERATED_ROOT = FRONTEND_ROOT / "src" / "generated"
SCRIPTS_ROOT = ROOT / "scripts"

# Make the api/ package importable.
sys.path.insert(0, str(API_ROOT))

from app.services.products.generator import (  # noqa: E402
    build_glass3d,
    compute_stats,
    course_hash,
    slugify_course,
)

SITE_ORIGIN = "https://www.splitthetee.com"
PROMPT_VERSION = "v1"


# ---------------------------------------------------------------------------
# Course sourcing
# ---------------------------------------------------------------------------

def load_curated() -> list[dict[str, Any]]:
    path = SCRIPTS_ROOT / "curated-courses.json"
    if not path.exists():
        return []
    with path.open() as f:
        return json.load(f)


async def load_from_mongo() -> list[dict[str, Any]]:
    """Load every course record in Mongo. Safe if MONGODB_URI is unset."""
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        return []
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except Exception:
        return []
    db_name = os.environ.get("MONGODB_DB_NAME", "splitthetee")
    client = AsyncIOMotorClient(uri)
    try:
        coll = client[db_name]["courses"]
        docs = [doc async for doc in coll.find({})]
        return [_normalize_mongo_course(d) for d in docs]
    finally:
        client.close()


def _normalize_mongo_course(doc: dict) -> dict:
    """Convert the Mongo course schema to the flat format the pipeline expects.

    Mongo stores tees as ``{"female": [...], "male": [...]}``, holes with
    ``ref`` instead of ``number``, and ``course_name`` instead of ``name``.
    """
    # Canonical name
    if "name" not in doc and "course_name" in doc:
        doc["name"] = doc["course_name"]

    # Flatten tees dict → list, tagging each entry with ``gender``
    raw_tees = doc.get("tees")
    if isinstance(raw_tees, dict):
        flat: list[dict] = []
        for gender, tee_list in raw_tees.items():
            if not isinstance(tee_list, list):
                continue
            for tee in tee_list:
                if isinstance(tee, dict):
                    tee.setdefault("gender", gender)
                    flat.append(tee)
        doc["tees"] = flat

    # Normalize hole ``ref`` → ``number`` in top-level holes
    for h in doc.get("holes") or []:
        if isinstance(h, dict) and "number" not in h and "ref" in h:
            h["number"] = h["ref"]

    return doc


def merge_courses(curated: list[dict], from_mongo: list[dict]) -> list[dict]:
    """Curated entries win on id collision."""
    by_id: dict[Any, dict] = {}
    for c in from_mongo:
        cid = c.get("course_id") or c.get("id")
        if cid is None:
            continue
        by_id[cid] = c
    for c in curated:
        cid = c.get("course_id") or c.get("id")
        if cid is None:
            continue
        by_id[cid] = c  # curated override
    return list(by_id.values())


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def read_cache() -> dict[str, Any]:
    path = SCRIPTS_ROOT / "cache.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def write_cache(cache: dict[str, Any]) -> None:
    (SCRIPTS_ROOT / "cache.json").write_text(json.dumps(cache, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# Glass3D + assets
# ---------------------------------------------------------------------------

def write_glass3d(slug: str, course: dict) -> tuple[str, str, list[int]]:
    """Write glass-3d.json and a flat glass-preview.svg.

    Returns (glass3d_url, svg_url, [svg_width, svg_height]).
    """
    out_dir = PUBLIC_ROOT / "products" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    data = build_glass3d(course, glass_number=1, glass_count=2)
    (out_dir / "glass-3d.json").write_text(json.dumps(data))
    svg = data.get("wrap_svg") or ""
    (out_dir / "glass-preview.svg").write_text(svg)
    return (
        f"/products/{slug}/glass-3d.json",
        f"/products/{slug}/glass-preview.svg",
        [900, 700],
    )


async def playwright_capture(slug: str, preview_port: int = 4173) -> list[str]:
    """Screenshot the hidden /render/glass/<slug> route at multiple angles.

    Returns the list of written paths (relative to public/). Returns [] if
    playwright isn't installed — stage is optional.
    """
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except Exception:
        print(f"[{slug}] playwright not installed — skipping capture")
        return []

    out_dir = PUBLIC_ROOT / "products" / slug
    written: list[str] = []
    angles = [
        ("front", "white", "glass-front.png"),
        ("three-quarter", "white", "glass-three-quarter.png"),
        ("side", "white", "glass-side.png"),
        ("front", "transparent", "glass-transparent.png"),
    ]
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--use-gl=swiftshader", "--disable-dev-shm-usage"])
        try:
            ctx = await browser.new_context(viewport={"width": 720, "height": 720})
            page = await ctx.new_page()
            for angle, bg, filename in angles:
                url = f"http://127.0.0.1:{preview_port}/render/glass/{slug}?angle={angle}&bg={bg}"
                await page.goto(url, wait_until="networkidle")
                try:
                    await page.wait_for_function("window.__renderReady === true", timeout=15_000)
                except Exception:
                    print(f"[{slug}] {angle}/{bg} never signalled ready — skipping")
                    continue
                await page.wait_for_timeout(500)  # one more frame for orbit
                if bg == "transparent":
                    await page.screenshot(path=str(out_dir / filename), omit_background=True)
                else:
                    canvas = page.locator("canvas").first
                    await canvas.screenshot(path=str(out_dir / filename))
                written.append(f"/products/{slug}/{filename}")
        finally:
            await browser.close()
    return written


def compose_patio(slug: str) -> str | None:
    """Composite glass-transparent.png over public/patio-stock.jpg."""
    try:
        from PIL import Image  # type: ignore
    except Exception:
        print(f"[{slug}] Pillow not installed — skipping patio composite")
        return None
    stock = PUBLIC_ROOT / "patio-stock.jpg"
    glass = PUBLIC_ROOT / "products" / slug / "glass-transparent.png"
    if not stock.exists() or not glass.exists():
        return None
    out = PUBLIC_ROOT / "products" / slug / "patio.jpg"
    with Image.open(stock) as bg, Image.open(glass) as gl:
        bg = bg.convert("RGB")
        # size the glass to ~55% of the bg height
        target_h = int(bg.height * 0.55)
        ratio = target_h / gl.height
        target_w = int(gl.width * ratio)
        gl = gl.resize((target_w, target_h))
        # place lower-right third
        x = bg.width - target_w - int(bg.width * 0.08)
        y = bg.height - target_h - int(bg.height * 0.12)
        bg.paste(gl, (x, y), gl if gl.mode == "RGBA" else None)
        bg.save(out, "JPEG", quality=85, optimize=True, progressive=True)
    return f"/products/{slug}/patio.jpg"


# ---------------------------------------------------------------------------
# AI content
# ---------------------------------------------------------------------------

AI_SYSTEM = (
    "You write short, factual product copy for laser-etched pint glasses "
    "made by Split the Tee. Never invent course history, designers, awards, "
    "or stats. Use only fields supplied in the user message. Tone: warm, "
    "confident, golf-literate, a little wry. Output strict JSON only."
)

AI_USER_TEMPLATE = """Course summary:
{course_json}

Return JSON with these fields only:
{{
  "headline": string (<=60 chars, no emoji),
  "description_html": HTML string with exactly three <p> tags, ~200 words total,
      allowed tags <p><strong><em>,
      no links, no images, no made-up facts,
  "bullets": 3 to 5 short factual bullets derived only from the supplied numbers.
}}"""


def allowed_html(raw: str) -> str:
    """Strip anything that isn't <p>/<strong>/<em>/<ul>/<li>/<h3>."""
    try:
        import bleach  # type: ignore
        return bleach.clean(
            raw,
            tags=["p", "strong", "em", "ul", "li", "h3"],
            attributes={},
            strip=True,
        )
    except Exception:
        # last-ditch: crude tag allowlist via regex
        allowed = {"p", "strong", "em", "ul", "li", "h3"}
        def repl(m):
            tag = m.group(2).lower()
            return m.group(0) if tag in allowed else ""
        return re.sub(r"<(/?)(\w+)[^>]*>", repl, raw)


def describe_course(course: dict, stats: dict) -> dict | None:
    """Call Anthropic to produce { headline, description_html, bullets }.

    Returns None if the API key isn't set or the call fails — the
    generator writes the rest of the product page regardless.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic  # type: ignore
    except Exception:
        print("anthropic SDK not installed — skipping AI description")
        return None

    payload = {
        "name": course.get("name"),
        "club_name": course.get("club_name"),
        "location": course.get("location"),
        "stats": stats,
        "tees": [
            {
                "tee_name": t.get("tee_name"),
                "par": t.get("par"),
                "yardage": t.get("yardage"),
                "rating": t.get("rating"),
                "slope": t.get("slope"),
            }
            for t in (course.get("tees") or [])[:3]
        ],
    }
    client = anthropic.Anthropic(api_key=api_key)
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=900,
            temperature=0.4,
            system=AI_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": AI_USER_TEMPLATE.format(course_json=json.dumps(payload, indent=2)),
                }
            ],
        )
    except Exception as exc:
        print(f"anthropic call failed: {exc}")
        return None
    text = "".join(
        block.text for block in msg.content if getattr(block, "type", None) == "text"
    )
    try:
        data = json.loads(text)
    except Exception:
        # model wrapped JSON in prose — try to extract the first {..} block
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except Exception:
            return None
    return {
        "headline": str(data.get("headline") or "")[:80],
        "description_html": allowed_html(str(data.get("description_html") or "")),
        "bullets": [str(b) for b in (data.get("bullets") or [])][:5],
    }


# ---------------------------------------------------------------------------
# Manifest + sitemap
# ---------------------------------------------------------------------------

def write_manifest(entries: list[dict]) -> None:
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = [
        {
            "slug": e["slug"],
            "name": e["name"],
            "club_name": e.get("club_name"),
            "city": e.get("city"),
            "state": e.get("state"),
            "country": e.get("country"),
            "par": e.get("stats", {}).get("total_par"),
            "yardage": e.get("stats", {}).get("total_yardage"),
            "hero_image": e.get("hero_image"),
        }
        for e in entries
    ]
    (GENERATED_ROOT / "products.json").write_text(json.dumps(manifest, indent=2))


def write_per_slug(entries: list[dict]) -> None:
    out = GENERATED_ROOT / "products"
    out.mkdir(parents=True, exist_ok=True)
    existing = {p.stem for p in out.glob("*.json")}
    current = set()
    for e in entries:
        current.add(e["slug"])
        (out / f"{e['slug']}.json").write_text(json.dumps(e, indent=2))
    for stale in existing - current:
        (out / f"{stale}.json").unlink(missing_ok=True)


def write_sitemap(entries: list[dict]) -> None:
    now = datetime.now(timezone.utc).date().isoformat()
    urls = [
        f"<url><loc>{SITE_ORIGIN}/</loc><lastmod>{now}</lastmod><priority>1.0</priority></url>",
        f"<url><loc>{SITE_ORIGIN}/products</loc><lastmod>{now}</lastmod><priority>0.9</priority></url>",
    ]
    for e in entries:
        urls.append(
            f"<url><loc>{SITE_ORIGIN}/products/{e['slug']}</loc>"
            f"<lastmod>{now}</lastmod><priority>0.8</priority></url>"
        )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    (PUBLIC_ROOT / "sitemap.xml").write_text(body)


def write_robots() -> None:
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /render/\n"
        "Disallow: /play/\n"
        f"Sitemap: {SITE_ORIGIN}/sitemap.xml\n"
    )
    (PUBLIC_ROOT / "robots.txt").write_text(body)


def gc_stale_products(keep_slugs: set[str]) -> None:
    root = PUBLIC_ROOT / "products"
    if not root.exists():
        return
    for child in root.iterdir():
        if child.is_dir() and child.name not in keep_slugs:
            for f in child.rglob("*"):
                if f.is_file():
                    f.unlink()
            child.rmdir()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def process_course(
    course: dict,
    cache: dict,
    *,
    force: bool,
    dry_run: bool,
    capture_images: bool,
) -> dict | None:
    slug = slugify_course(course)
    if not slug:
        return None
    input_hash = course_hash(course)
    cached = cache.get(slug) or {}
    unchanged = cached.get("input_hash") == input_hash and not force

    try:
        stats = compute_stats(course)
    except Exception as exc:
        print(f"[{slug}] stats failed: {exc}")
        return None

    # Glass3D (cheap, reruns every time the course changes) + flat SVG preview
    glass3d_url = None
    svg_preview = None
    try:
        glass3d_url, svg_preview, _ = write_glass3d(slug, course)
    except Exception as exc:
        print(f"[{slug}] glass-3d failed: {exc}")

    hero_image = svg_preview
    patio_image = None
    gallery: list[str] = [svg_preview] if svg_preview else []

    if not dry_run and capture_images and (not unchanged or force):
        captured = await playwright_capture(slug)
        if captured:
            hero_image = captured[0]
            gallery = [*captured, *gallery]
        patio_image = compose_patio(slug)
    elif cached.get("hero_image"):
        # Prefer the cached (Playwright) hero over the fresh SVG preview.
        hero_image = cached.get("hero_image")
        patio_image = cached.get("patio_image")
        cached_gallery = cached.get("gallery") or []
        gallery = [*cached_gallery, *(g for g in gallery if g not in cached_gallery)]

    # AI content (cached by input hash)
    content = None
    if unchanged and cached.get("content"):
        content = cached["content"]
    elif not dry_run:
        content = describe_course(course, stats)

    if not content:
        # Fallback copy so the page still ships.
        loc_bits = course.get("location") or {}
        location_str = ", ".join(
            p for p in [loc_bits.get("city"), loc_bits.get("state")] if p
        )
        content = {
            "headline": f"{course.get('name')} — your course, on a pint glass.",
            "description_html": (
                f"<p>A pint glass etched with the nine-hole front and back of "
                f"{course.get('name')}{f', {location_str}' if location_str else ''}. "
                f"Pour a beer and the line lands right where your score does.</p>"
                f"<p>Each set comes with two glasses — one for the front nine, one for "
                f"the back. Track your round as you drink it.</p>"
                f"<p>Preorder now for the first run.</p>"
            ),
            "bullets": [
                f"Par {stats['total_par']}",
                f"{stats['total_yardage']} yards",
                f"{stats['holes']} holes etched across 2 glasses",
            ],
        }

    loc = course.get("location") or {}
    entry = {
        "slug": slug,
        "course_id": course.get("course_id") or course.get("id") or 0,
        "name": course.get("name") or course.get("club_name") or slug,
        "club_name": course.get("club_name"),
        "city": loc.get("city"),
        "state": loc.get("state"),
        "country": loc.get("country"),
        "stats": stats,
        "content": content,
        "glass3d_url": glass3d_url,
        "hero_image": hero_image,
        "patio_image": patio_image,
        "gallery": gallery,
    }

    cache[slug] = {
        "input_hash": input_hash,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "content": content,
        "hero_image": hero_image,
        "patio_image": patio_image,
        "gallery": gallery,
    }
    return entry


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Only process the slug matching this value")
    parser.add_argument("--force", action="store_true", help="Ignore cache")
    parser.add_argument("--dry-run", action="store_true", help="Manifests + JSON only; no Playwright/AI")
    parser.add_argument("--no-capture", action="store_true", help="Skip Playwright even if installed")
    args = parser.parse_args()

    curated = load_curated()
    mongo = await load_from_mongo()
    all_courses = merge_courses(curated, mongo)
    if args.only:
        all_courses = [c for c in all_courses if slugify_course(c) == args.only]

    print(f"Processing {len(all_courses)} course(s)")

    cache = read_cache()
    entries: list[dict] = []
    for course in all_courses:
        entry = await process_course(
            course,
            cache,
            force=args.force,
            dry_run=args.dry_run,
            capture_images=not args.no_capture,
        )
        if entry:
            entries.append(entry)
            print(f"  ✓ {entry['slug']}")

    entries.sort(key=lambda e: e["name"])
    write_manifest(entries)
    write_per_slug(entries)
    write_sitemap(entries)
    write_robots()
    write_cache(cache)
    gc_stale_products({e["slug"] for e in entries})

    print(
        f"Done. {len(entries)} products, manifest -> {GENERATED_ROOT / 'products.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
