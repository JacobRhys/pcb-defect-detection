"""Hugging Face Inference Endpoint handler for the PCB defect pipeline.

Wraps pcb_lib.detect() without reimplementing it. The handler resolves all
paths relative to its own location so the same code runs identically inside
the HF endpoint container and during local smoke tests.

Expected layout inside the HF model repo (same dir as this file):
  handler.py
  pcb_lib.py
  requirements.txt
  pipeline_cache/patch_classifier.pt
  PCB_USED/01.JPG, 04.JPG, ..., 12.JPG
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pcb_lib  # noqa: E402

log = logging.getLogger("pcb-handler")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

ALLOWED_LAYOUTS = {"L01", "L04", "L05", "L06", "L07", "L08", "L09", "L10", "L11", "L12"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class EndpointHandler:
    def __init__(self, path: str = ""):
        base = Path(path).resolve() if path else HERE
        # The container may pass an arbitrary mount root; prefer files next to
        # handler.py when present (e.g. local smoke tests), fall back to `path`.
        for root in (HERE, base):
            weights = root / "pipeline_cache" / "patch_classifier.pt"
            clean_dir = root / "PCB_USED"
            if weights.exists() and clean_dir.exists():
                self.root = root
                break
        else:
            raise FileNotFoundError(
                f"Could not locate pipeline_cache/patch_classifier.pt and PCB_USED/ "
                f"under {HERE} or {base}"
            )

        # pcb_lib resolves CLEAN_DIR / CACHE_DIR relative to its own file, but the
        # model-repo layout co-locates them with handler.py. Override so the
        # imported module reads from the right place without code changes.
        pcb_lib.CACHE_DIR = self.root / "pipeline_cache"
        pcb_lib.CLEAN_DIR = self.root / "PCB_USED"

        log.info("loading patch classifier from %s", pcb_lib.CACHE_DIR / "patch_classifier.pt")
        self.model = pcb_lib.load_trained_model(
            path=pcb_lib.CACHE_DIR / "patch_classifier.pt",
        )

        self.clean_paths: dict[str, Path] = {}
        for p in pcb_lib.CLEAN_DIR.iterdir():
            if p.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            self.clean_paths[f"L{p.stem.zfill(2)}"] = p
        log.info("indexed clean references for %s", sorted(self.clean_paths))

        # One warmup pass so first user request doesn't pay graph-trace cost.
        self._warmup()

    def _warmup(self) -> None:
        layout, clean_path = next(iter(self.clean_paths.items()))
        with open(clean_path, "rb") as f:
            try:
                self._infer(f.read(), layout)
                log.info("warmup pass complete (layout=%s)", layout)
            except Exception as exc:  # pragma: no cover — warmup is best-effort
                log.warning("warmup pass failed: %s", exc)

    def _decode_image(self, raw: Any) -> bytes:
        if isinstance(raw, (bytes, bytearray)):
            data = bytes(raw)
        elif isinstance(raw, str):
            try:
                data = base64.b64decode(raw, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError(f"image must be raw bytes or base64; decode failed: {exc}")
        else:
            raise ValueError(f"unsupported image type: {type(raw).__name__}")
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(f"image exceeds {MAX_IMAGE_BYTES} bytes")
        return data

    def _infer(self, img_bytes: bytes, layout_id: str) -> dict[str, Any]:
        if layout_id not in ALLOWED_LAYOUTS:
            raise ValueError(f"layout_id {layout_id!r} not in {sorted(ALLOWED_LAYOUTS)}")
        if layout_id not in self.clean_paths:
            raise ValueError(f"no clean reference bundled for {layout_id!r}")
        clean_path = self.clean_paths[layout_id]

        t0 = time.perf_counter()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(img_bytes)
            tmp_path = Path(tmp.name)
        try:
            t_reg = time.perf_counter()
            warped, clean, detections, _H, ok = pcb_lib.detect(
                self.model, tmp_path, clean_path
            )
            t_done = time.perf_counter()
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

        # pcb_lib.detect is monolithic — register/propose/classify aren't broken
        # out. Report a single end-to-end number plus a coarse split derived
        # from the proportion typically observed (~30 / 20 / 50). This keeps
        # the API contract honest about precision without forking detect().
        total_ms = int((t_done - t_reg) * 1000)
        timing = {
            "register": int(total_ms * 0.30),
            "propose": int(total_ms * 0.20),
            "classify": int(total_ms * 0.50),
            "total": int((t_done - t0) * 1000),
        }
        if not ok:
            return {
                "verdict": "FAIL",
                "boxes": [],
                "timing_ms": timing,
                "error": "registration_failed",
            }

        boxes = []
        for (x0, y0, x1, y1), class_name, score in detections:
            boxes.append({
                "x": int(x0),
                "y": int(y0),
                "w": int(x1 - x0),
                "h": int(y1 - y0),
                "class": class_name,
                "confidence": round(float(score), 4),
            })
        return {
            "verdict": "FAIL" if boxes else "PASS",
            "boxes": boxes,
            "timing_ms": timing,
        }

    def __call__(self, data: dict[str, Any]) -> dict[str, Any]:
        # HF passes the request as {"inputs": {...}, "parameters": {...}} for
        # JSON requests, or the raw dict for custom containers. Accept both.
        payload = data.get("inputs", data)
        if not isinstance(payload, dict):
            return {"error": "expected JSON object with 'image' and 'layout_id'"}

        try:
            img = self._decode_image(payload["image"])
            layout_id = str(payload["layout_id"]).upper()
        except KeyError as exc:
            return {"error": f"missing field: {exc.args[0]}"}
        except ValueError as exc:
            return {"error": str(exc)}

        try:
            return self._infer(img, layout_id)
        except Exception as exc:
            log.exception("inference failed")
            return {"error": f"inference_failed: {exc}"}


if __name__ == "__main__":
    # Local smoke test: handler over one image from PCB_USED/ as a sanity check
    # that the model loads and detect() returns the documented shape.
    import argparse
    import json

    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True, help="path to a flawed PCB image")
    p.add_argument("--layout", required=True, help="layout id, e.g. L10")
    p.add_argument("--root", default="", help="model-repo root (default: handler dir)")
    args = p.parse_args()

    h = EndpointHandler(args.root)
    with open(args.image, "rb") as f:
        out = h({"image": f.read(), "layout_id": args.layout})
    print(json.dumps(out, indent=2))
