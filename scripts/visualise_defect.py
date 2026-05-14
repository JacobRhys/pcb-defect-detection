"""Side-by-side viewer: clean PCB vs flawed PCB with annotated bounding boxes.

Usage:
    python visualise_defect.py PCB_DATASET/images/Missing_hole/01_missing_hole_01.jpg
    python visualise_defect.py 01_missing_hole_01            # bare stem also works
    python visualise_defect.py                                # picks a random example
"""

from __future__ import annotations

import argparse
import random
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image

ROOT = Path(__file__).parent
DATASET = ROOT / "PCB_DATASET"
IMAGES_DIR = DATASET / "images"
ANNOT_DIR = DATASET / "Annotations"
CLEAN_DIR = DATASET / "PCB_USED"


def resolve_sample(arg: str | None) -> Path:
    """Turn a user argument into an absolute path to a flawed image."""
    if arg is None:
        all_imgs = list(IMAGES_DIR.rglob("*.jpg")) + list(IMAGES_DIR.rglob("*.JPG"))
        if not all_imgs:
            sys.exit(f"No images found under {IMAGES_DIR}")
        return random.choice(all_imgs)

    p = Path(arg)
    if p.is_file():
        return p

    stem = p.stem if p.suffix else arg
    matches = list(IMAGES_DIR.rglob(f"{stem}.*"))
    if not matches:
        sys.exit(f"Could not find image for '{arg}' under {IMAGES_DIR}")
    return matches[0]


def find_annotation(img_path: Path) -> Path:
    flaw_type = img_path.parent.name
    xml_path = ANNOT_DIR / flaw_type / f"{img_path.stem}.xml"
    if not xml_path.is_file():
        sys.exit(f"Annotation missing: {xml_path}")
    return xml_path


def find_clean(img_path: Path) -> Path:
    layout_id = img_path.stem.split("_")[0]
    candidates = list(CLEAN_DIR.glob(f"{layout_id}.*"))
    if not candidates:
        sys.exit(f"No clean example for layout {layout_id} in {CLEAN_DIR}")
    return candidates[0]


def parse_boxes(xml_path: Path) -> list[tuple[str, int, int, int, int]]:
    root = ET.parse(xml_path).getroot()
    boxes = []
    for obj in root.findall("object"):
        name = obj.findtext("name", default="?")
        b = obj.find("bndbox")
        boxes.append((
            name,
            int(b.findtext("xmin")),
            int(b.findtext("ymin")),
            int(b.findtext("xmax")),
            int(b.findtext("ymax")),
        ))
    return boxes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image", nargs="?", help="Flawed image path or stem (omit for random)")
    args = ap.parse_args()

    flaw_path = resolve_sample(args.image)
    xml_path = find_annotation(flaw_path)
    clean_path = find_clean(flaw_path)
    boxes = parse_boxes(xml_path)

    flaw_img = Image.open(flaw_path)
    clean_img = Image.open(clean_path)

    fig, (ax_clean, ax_flaw) = plt.subplots(1, 2, figsize=(16, 7))

    ax_clean.imshow(clean_img)
    ax_clean.set_title(f"Clean reference — {clean_path.name}")
    ax_clean.axis("off")

    ax_flaw.imshow(flaw_img)
    ax_flaw.set_title(f"{flaw_path.parent.name} — {flaw_path.name}  ({len(boxes)} box{'es' if len(boxes) != 1 else ''})")
    ax_flaw.axis("off")

    for name, xmin, ymin, xmax, ymax in boxes:
        rect = Rectangle(
            (xmin, ymin), xmax - xmin, ymax - ymin,
            linewidth=2, edgecolor="red", facecolor="none",
        )
        ax_flaw.add_patch(rect)
        ax_flaw.text(
            xmin, max(ymin - 8, 0), name,
            color="white", fontsize=8,
            bbox=dict(facecolor="red", edgecolor="none", pad=1),
        )

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
