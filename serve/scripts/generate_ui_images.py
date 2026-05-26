#!/usr/bin/env python3
"""Generate UI mock images from docs/UI_PROMPTS.md via local image API,
then rebuild docs/UI_GALLERY.md to match what currently lives in docs/ui-images/.

Local API contract (already running by user):
    POST http://localhost:7000/v1/images/generations
    Authorization: Bearer chatgpt2api
    body: { model, prompt, n, size, response_format: "b64_json" }

Usage
-----
    # Generate every missing image, then rebuild gallery:
    python scripts/generate_ui_images.py

    # Only generate the first N missing images (great for smoke-testing):
    python scripts/generate_ui_images.py --limit 5

    # Skip generation, just rebuild the gallery from what exists on disk:
    python scripts/generate_ui_images.py --gallery-only

    # Force regenerate everything (overwrites existing PNGs):
    python scripts/generate_ui_images.py --redo all

    # Force regenerate only entries whose slug contains a substring:
    python scripts/generate_ui_images.py --redo onboarding

Idempotency
-----------
- Existing PNGs in docs/ui-images/ are SKIPPED unless --redo is passed.
- The gallery .md is ALWAYS rebuilt from the current state of ui-images/.
- Safe to interrupt and re-run; only missing images are produced.

Stdlib-only — no pip install required.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "UI_PROMPTS.md"
IMG_DIR = ROOT / "docs" / "ui-images"
GALLERY = ROOT / "docs" / "UI_GALLERY.md"

API_URL = "http://localhost:7000/v1/images/generations"
API_KEY = "chatgpt2api"
MODEL = "gpt-image-2"

CONCURRENCY = 6
MAX_RETRIES = 4
REQUEST_TIMEOUT = 240  # seconds per request

# §00 is the canonical preamble reference; every other code block already
# embeds the same preamble, so generating §00 itself would be a duplicate.
SKIP_H2_PREFIXES = ("§00",)

# ---------------------------------------------------------------------------
# Doc parsing
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """ASCII-only, filesystem-safe slug. CJK is stripped so filenames stay
    portable across editors / browsers serving the gallery."""
    text = re.sub(r"[（）()·,，:：—\-]+", " ", text)
    text = re.sub(r"[^A-Za-z0-9\s]", "", text).strip().lower()
    text = re.sub(r"\s+", "-", text)
    return text[:80].strip("-") or "block"


def pick_size(title: str, body: str, h2: str) -> str:
    """Choose 1:1 / 16:9 / 4:3 / 3:4 / 9:16 based on explicit dimensions in
    the prompt body, else heuristic by section."""
    m = re.search(r"(\d{3,4})\s*[×x]\s*(\d{3,4})", body)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        ratio = w / h
        if ratio > 1.55:
            return "16:9"
        if ratio > 1.20:
            return "4:3"
        if ratio > 0.85:
            return "1:1"
        if ratio > 0.65:
            return "3:4"
        return "9:16"
    # heuristic fallbacks
    if any(k in title for k in (
        "S1.", "S2.", "S3.", "S4.", "S5.", "S5b.", "S6.", "S7.", "S8.",
        "J1.", "J2.", "J3.", "Dashboard", "Browser", "Storyboard",
    )):
        return "16:9"
    if any(k in title for k in ("M1.", "M2.", "M3.", "M4.", "Modal", "Drawer", "Overlay")):
        return "4:3"
    return "1:1"


def parse_doc() -> list[dict]:
    text = DOC.read_text(encoding="utf-8")
    lines = text.split("\n")
    items: list[dict] = []
    h2 = h3 = h4 = ""
    i = 0
    n = len(lines)
    counter = 0

    while i < n:
        line = lines[i]
        if line.startswith("## "):
            h2 = line[3:].strip()
            h3 = h4 = ""
        elif line.startswith("### "):
            h3 = line[4:].strip()
            h4 = ""
        elif line.startswith("#### "):
            h4 = line[5:].strip()
        elif line.strip() == "```":
            j = i + 1
            while j < n and lines[j].strip() != "```":
                j += 1
            body = "\n".join(lines[i + 1:j])
            i = j + 1

            # skip §00 reference block (it's the canonical preamble)
            if any(h2.startswith(p) for p in SKIP_H2_PREFIXES):
                continue

            title = h4 or h3 or h2 or "untitled"
            counter += 1
            slug = slugify(title)
            items.append({
                "idx": counter,
                "h2": h2,
                "h3": h3,
                "h4": h4,
                "title": title,
                "prompt": body,
                "size": pick_size(title, body, h2),
                "slug": slug,
                "filename": f"{counter:03d}-{slug}.png",
            })
            continue
        i += 1
    return items


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def post_json(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def generate_one(item: dict) -> bytes | None:
    payload = {
        "model": MODEL,
        "prompt": item["prompt"],
        "n": 1,
        "size": item["size"],
        "response_format": "b64_json",
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            data = post_json(API_URL, payload, headers, REQUEST_TIMEOUT)
            b64 = data["data"][0]["b64_json"]
            return base64.b64decode(b64)
        except Exception as e:  # noqa: BLE001 - we deliberately catch all
            last_err = e
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                print(
                    f"  [{item['filename']}] retry {attempt}/{MAX_RETRIES} "
                    f"in {wait}s ({type(e).__name__}: {e})",
                    flush=True,
                )
                time.sleep(wait)
    print(
        f"  [{item['filename']}] FAIL after {MAX_RETRIES} attempts: {last_err}",
        flush=True,
    )
    return None


# ---------------------------------------------------------------------------
# Gallery
# ---------------------------------------------------------------------------

def build_gallery(items: list[dict], available_files: set[str]) -> None:
    produced = sum(1 for it in items if it["filename"] in available_files)
    out = [
        "# UI 提示词图集 — RAG-KG Copilot",
        "",
        f"> 自动生成自 `docs/UI_PROMPTS.md`（{len(items)} 条提示词，"
        f"已生成 **{produced}** 张）。",
        f"> 每张图通过本地 `{API_URL}` (`model={MODEL}`) 接口批量生成。",
        f"> 缺失的图说明尚未生成或生成失败 — 重跑 "
        f"`python scripts/generate_ui_images.py` 即可补齐。",
        "",
        "---",
        "",
    ]
    current_h2: str | None = None
    for item in items:
        if item["h2"] != current_h2:
            current_h2 = item["h2"]
            out.append(f"## {current_h2}")
            out.append("")
        out.append(f"### {item['title']}")
        out.append("")
        out.append(f"`size: {item['size']}`  ·  `slug: {item['slug']}`")
        out.append("")
        if item["filename"] in available_files:
            out.append(f"![{item['title']}](ui-images/{item['filename']})")
        else:
            out.append(
                f"> ⚠️ image not yet generated — run "
                f"`python scripts/generate_ui_images.py` to create "
                f"`ui-images/{item['filename']}`"
            )
        out.append("")
    GALLERY.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {GALLERY.relative_to(ROOT)} ({produced}/{len(items)} images present)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "--limit", type=int, default=0,
        help="Generate only the first N missing images (0 = all).",
    )
    p.add_argument(
        "--gallery-only", action="store_true",
        help="Skip API calls; just rebuild docs/UI_GALLERY.md from existing PNGs.",
    )
    p.add_argument(
        "--redo", default="",
        help='Force regenerate: "all" or a slug-substring (e.g. "onboarding").',
    )
    args = p.parse_args()

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    items = parse_doc()
    print(f"Parsed {len(items)} prompts from {DOC.relative_to(ROOT)}")

    if args.gallery_only:
        available = {p.name for p in IMG_DIR.glob("*.png")}
        build_gallery(items, available)
        return 0

    existing = {p.name for p in IMG_DIR.glob("*.png")}

    todo: list[dict] = []
    for it in items:
        if args.redo == "all":
            todo.append(it)
        elif args.redo and args.redo in it["slug"]:
            todo.append(it)
        elif it["filename"] not in existing:
            todo.append(it)

    if args.limit > 0:
        todo = todo[: args.limit]

    print(f"Already generated: {len(existing)} PNGs in docs/ui-images/")
    print(f"To generate now:   {len(todo)}")

    if not todo:
        print("Nothing to do (use --redo all to force regenerate).")
        build_gallery(items, existing)
        return 0

    print(
        f"Concurrency: {CONCURRENCY}  ·  Retries: {MAX_RETRIES}  "
        f"·  Timeout: {REQUEST_TIMEOUT}s\n"
    )

    lock = Lock()
    state = {"done": 0, "success": 0}

    def worker(item: dict) -> bool:
        t0 = time.time()
        img = generate_one(item)
        elapsed = time.time() - t0
        with lock:
            state["done"] += 1
            ok = img is not None
            if ok:
                (IMG_DIR / item["filename"]).write_bytes(img)
                state["success"] += 1
            tag = "OK  " if ok else "FAIL"
            print(
                f"{tag} [{state['done']:3d}/{len(todo)}] "
                f"({elapsed:5.1f}s, {item['size']:>4s}) {item['filename']}",
                flush=True,
            )
        return ok

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = [ex.submit(worker, it) for it in todo]
        for _ in as_completed(futures):
            pass

    print(
        f"\nDone: {state['success']}/{len(todo)} succeeded, "
        f"{len(todo) - state['success']} failed."
    )

    available = {p.name for p in IMG_DIR.glob("*.png")}
    build_gallery(items, available)
    return 0 if state["success"] == len(todo) else 1


if __name__ == "__main__":
    sys.exit(main())
