"""Stage demo PCB images for the web frontend.

Reads PCB_DATASET locally, picks images from the held-out layouts
(10, 11, 12) across all six defect classes, and writes them plus a
manifest.json into web/public/samples/.

This script is developer-only — the output IS committed (a few MB total).
The web demo does not depend on PCB_DATASET at runtime; only on the
contents of web/public/samples/.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "PCB_DATASET"
IMAGES_DIR = DATASET / "images"

# images/ uses TitleCase folder names; class labels in the API contract
# (and benchmark.ipynb) are lowercase snake_case. Map between them.
FLAW_DIRS = {
    "missing_hole":    "Missing_hole",
    "mouse_bite":      "Mouse_bite",
    "open_circuit":    "Open_circuit",
    "short":           "Short",
    "spur":            "Spur",
    "spurious_copper": "Spurious_copper",
}

HELD_OUT_LAYOUTS = {"10", "11", "12"}
# The detection pipeline (ORB registration, CLAHE diff proposals, 96-px
# classifier crops) was tuned on the original dataset images. Re-encoding or
# resizing the flaw image changes the registration/diff behaviour relative to
# the bundled clean references, so the staged web samples should preserve the
# original pixels.


def _layout_of(stem: str) -> str | None:
    """Filenames look like `10_short_01` — first segment is the layout id."""
    parts = stem.split("_")
    return parts[0] if parts else None


def collect_candidates() -> list[tuple[Path, str, str]]:
    out: list[tuple[Path, str, str]] = []
    for label, folder in FLAW_DIRS.items():
        d = IMAGES_DIR / folder
        if not d.is_dir():
            print(f"warn: missing {d}", file=sys.stderr)
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            layout = _layout_of(p.stem)
            if layout in HELD_OUT_LAYOUTS:
                out.append((p, label, layout))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(ROOT / "web" / "public" / "samples"))
    p.add_argument("--n", type=int, default=40, help="max images to stage")
    p.add_argument("--seed", type=int, default=20260514)
    args = p.parse_args()

    out_dir = Path(args.out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = collect_candidates()
    if not candidates:
        print("error: no candidates — is PCB_DATASET/ present?", file=sys.stderr)
        sys.exit(1)

    # Stratified pick across (layout, class) so the demo shows variety.
    rng = random.Random(args.seed)
    buckets: dict[tuple[str, str], list[Path]] = {}
    for path, label, layout in candidates:
        buckets.setdefault((layout, label), []).append(path)

    keys = list(buckets)
    rng.shuffle(keys)
    picks: list[tuple[Path, str, str]] = []
    while len(picks) < args.n and keys:
        for k in list(keys):
            bucket = buckets[k]
            if not bucket:
                keys.remove(k)
                continue
            idx = rng.randrange(len(bucket))
            picks.append((bucket.pop(idx), k[1], k[0]))
            if len(picks) >= args.n:
                break

    manifest = []
    for i, (src, label, layout) in enumerate(picks):
        img = cv2.imread(str(src), cv2.IMREAD_COLOR)
        if img is None:
            print(f"warn: failed to read {src}", file=sys.stderr)
            continue
        out_name = f"L{layout}_{label}_{i:02d}.jpg"
        out_path = out_dir / out_name
        shutil.copy2(src, out_path)
        manifest.append({
            "file": out_name,
            "layout_id": f"L{layout}",
            "expected_class": label,
            "width": int(img.shape[1]),
            "height": int(img.shape[0]),
        })

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    total_kb = sum((out_dir / m["file"]).stat().st_size for m in manifest) // 1024
    print(f"wrote {len(manifest)} images + manifest.json to {out_dir} ({total_kb} KB total)")


if __name__ == "__main__":
    main()
