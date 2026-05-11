"""Shared helpers for the PCB defect detection pipeline.

Imported by `pcb_pipeline.ipynb` (training) and `benchmark.ipynb` (evaluation).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models

ROOT = Path(__file__).parent
DATASET = ROOT / "PCB_DATASET"
IMAGES_DIR = DATASET / "images"
ANNOT_DIR = DATASET / "Annotations"
CLEAN_DIR = DATASET / "PCB_USED"
CACHE_DIR = ROOT / "pipeline_cache"

CLASSES = ["none", "missing_hole", "mouse_bite", "open_circuit", "short", "spur", "spurious_copper"]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}

CROP = 96

DEVICE = (
    torch.device("mps") if torch.backends.mps.is_available()
    else torch.device("cuda") if torch.cuda.is_available()
    else torch.device("cpu")
)


@dataclass
class Sample:
    img_path: Path
    xml_path: Path
    clean_path: Path
    layout: str
    flaw_type: str
    boxes: list


def parse_boxes(xml_path: Path):
    root = ET.parse(xml_path).getroot()
    out = []
    for obj in root.findall("object"):
        name = obj.findtext("name", default="?")
        b = obj.find("bndbox")
        out.append((
            name,
            int(b.findtext("xmin")), int(b.findtext("ymin")),
            int(b.findtext("xmax")), int(b.findtext("ymax")),
        ))
    return out


def build_index() -> list[Sample]:
    clean_by_layout = {p.stem: p for p in CLEAN_DIR.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}}
    samples = []
    for xml_path in ANNOT_DIR.rglob("*.xml"):
        flaw_type = xml_path.parent.name
        stem = xml_path.stem
        layout = stem.split("_")[0]
        if layout not in clean_by_layout:
            continue
        imgs = list((IMAGES_DIR / flaw_type).glob(f"{stem}.*"))
        if not imgs:
            continue
        samples.append(Sample(
            img_path=imgs[0],
            xml_path=xml_path,
            clean_path=clean_by_layout[layout],
            layout=layout,
            flaw_type=flaw_type,
            boxes=parse_boxes(xml_path),
        ))
    return samples


def imread_color(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


_ORB = cv2.ORB_create(nfeatures=4000)
_BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)


def register(flaw_rgb: np.ndarray, clean_rgb: np.ndarray):
    g1 = cv2.cvtColor(flaw_rgb, cv2.COLOR_RGB2GRAY)
    g2 = cv2.cvtColor(clean_rgb, cv2.COLOR_RGB2GRAY)
    k1, d1 = _ORB.detectAndCompute(g1, None)
    k2, d2 = _ORB.detectAndCompute(g2, None)
    if d1 is None or d2 is None or len(k1) < 10 or len(k2) < 10:
        return flaw_rgb, np.eye(3), False
    matches = sorted(_BF.match(d1, d2), key=lambda m: m.distance)[:500]
    if len(matches) < 8:
        return flaw_rgb, np.eye(3), False
    src = np.float32([k1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst = np.float32([k2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    H, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if H is None:
        return flaw_rgb, np.eye(3), False
    h, w = g2.shape
    return cv2.warpPerspective(flaw_rgb, H, (w, h)), H, True


def warp_boxes(boxes, H):
    out = []
    for label, x0, y0, x1, y1 in boxes:
        pts = np.float32([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]).reshape(-1, 1, 2)
        w = cv2.perspectiveTransform(pts, H).reshape(-1, 2)
        out.append((
            label,
            int(w[:, 0].min()), int(w[:, 1].min()),
            int(w[:, 0].max()), int(w[:, 1].max()),
        ))
    return out


_CLAHE = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))


def _equalise(img_rgb: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
    lab[..., 0] = _CLAHE.apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def _mask_border(mask: np.ndarray, border: int) -> None:
    mask[:border, :] = 0; mask[-border:, :] = 0
    mask[:, :border] = 0; mask[:, -border:] = 0


def propose(warped_rgb: np.ndarray, clean_rgb: np.ndarray,
            thresh: int = 15, min_area: int = 8, max_area: int = 40000,
            dilate_px: int = 10, border: int = 20):
    a = cv2.GaussianBlur(_equalise(warped_rgb), (5, 5), 0)
    b = cv2.GaussianBlur(_equalise(clean_rgb), (5, 5), 0)
    diff = np.max(cv2.absdiff(a, b), axis=2)
    _, mask = cv2.threshold(diff, thresh, 255, cv2.THRESH_BINARY)
    mask = cv2.dilate(mask, np.ones((dilate_px, dilate_px), np.uint8))
    _mask_border(mask, border)
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    proposals = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < min_area or area > max_area:
            continue
        proposals.append((x, y, x + w, y + h))
    return proposals


def iou(a, b):
    ax0, ay0, ax1, ay1 = a; bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    if inter == 0:
        return 0.0
    return inter / ((ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter)


def safe_crop(img: np.ndarray, cx: int, cy: int, size: int = CROP) -> np.ndarray:
    h, w = img.shape[:2]
    half = size // 2
    x0 = max(0, min(cx - half, w - size))
    y0 = max(0, min(cy - half, h - size))
    return img[y0:y0 + size, x0:x0 + size]


def build_model(num_classes: int = len(CLASSES)) -> nn.Module:
    m = models.resnet18(weights=None)
    old = m.conv1
    m.conv1 = nn.Conv2d(6, old.out_channels, kernel_size=old.kernel_size,
                        stride=old.stride, padding=old.padding, bias=False)
    m.fc = nn.Linear(m.fc.in_features, num_classes)
    return m


_MEAN = torch.tensor([0.485, 0.456, 0.406, 0.485, 0.456, 0.406]).view(6, 1, 1)
_STD = torch.tensor([0.229, 0.224, 0.225, 0.229, 0.224, 0.225]).view(6, 1, 1)


def crop_to_tensor(crop6: np.ndarray) -> torch.Tensor:
    t = torch.from_numpy(crop6).permute(2, 0, 1).float() / 255.0
    return (t - _MEAN) / _STD


@torch.no_grad()
def detect(model: nn.Module, img_path: Path, clean_path: Path,
           score_thresh: float = 0.5, device: torch.device = DEVICE):
    """Full pipeline: register → propose → classify. Returns (warped, clean, detections, H, ok)."""
    flaw = imread_color(img_path); clean = imread_color(clean_path)
    warped, H, ok = register(flaw, clean)
    if not ok:
        return warped, clean, [], H, False
    props = propose(warped, clean)
    if not props:
        return warped, clean, [], H, True
    batch = []
    keep_idx = []
    for i, (x0, y0, x1, y1) in enumerate(props):
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        cw = safe_crop(warped, cx, cy); cc = safe_crop(clean, cx, cy)
        if cw.shape[:2] != (CROP, CROP) or cc.shape[:2] != (CROP, CROP):
            continue
        batch.append(crop_to_tensor(np.concatenate([cw, cc], axis=2)))
        keep_idx.append(i)
    detections = []
    if batch:
        x = torch.stack(batch).to(device)
        probs = F.softmax(model(x), dim=1).cpu().numpy()
        for vi, p in zip(keep_idx, probs):
            cls = int(p.argmax()); score = float(p[cls])
            if cls == 0 or score < score_thresh:
                continue
            detections.append((props[vi], CLASSES[cls], score))
    return warped, clean, detections, H, True


def load_trained_model(path: Path = CACHE_DIR / "patch_classifier.pt",
                       device: torch.device = DEVICE) -> nn.Module:
    model = build_model()
    state = torch.load(path, map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.to(device).eval()
    return model
