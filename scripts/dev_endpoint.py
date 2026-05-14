"""Local development inference server.

Wraps service/handler.py:EndpointHandler in a stdlib HTTP server so the web
demo can talk to the real pipeline on http://127.0.0.1:8000 without needing
a deployed Hugging Face endpoint. Vite's dev proxy forwards /api/* here.

This is a developer convenience — it bypasses the Cloudflare Pages Function
for local iteration. The Function itself is still exercised by CI and by
the deployed environment.

Run:
    python3.11 scripts/dev_endpoint.py
"""

from __future__ import annotations

import argparse
import cgi
import json
import logging
import os
import sys
import tempfile
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "service"))
sys.path.insert(0, str(REPO))

from handler import EndpointHandler  # noqa: E402

log = logging.getLogger("dev-endpoint")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

HANDLER: EndpointHandler | None = None


def stage_model_repo() -> Path:
    """Mirror the HF model-repo layout in a tmp dir so EndpointHandler resolves
    weights and clean references from a single root, just like in production."""
    root = Path(tempfile.mkdtemp(prefix="aifi-dev-"))
    shutil.copy2(REPO / "pcb_lib.py", root / "pcb_lib.py")
    shutil.copy2(REPO / "service" / "handler.py", root / "handler.py")
    (root / "pipeline_cache").mkdir()
    shutil.copy2(REPO / "pipeline_cache" / "patch_classifier.pt",
                 root / "pipeline_cache" / "patch_classifier.pt")
    (root / "PCB_USED").mkdir()
    for jpg in (REPO / "PCB_DATASET" / "PCB_USED").glob("*.JPG"):
        shutil.copy2(jpg, root / "PCB_USED" / jpg.name)
    log.info("staged model-repo layout at %s", root)
    return root


class Handler(BaseHTTPRequestHandler):
    server_version = "AIFI-DevEndpoint/0.1"

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type, authorization")

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self._cors()
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        # The warmup ping from the frontend hits HEAD /api/detect.
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._json(200, {"ok": True, "service": "aifi-dev-endpoint"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/api/detect", "/detect"):
            self._json(404, {"error": f"no such path {self.path}"})
            return
        if HANDLER is None:
            self._json(503, {"error": "handler not ready"})
            return
        ct = self.headers.get("Content-Type", "")
        try:
            if ct.startswith("multipart/form-data"):
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": ct},
                )
                if "image" not in form or "layout_id" not in form:
                    self._json(400, {"error": "missing image or layout_id"})
                    return
                image_bytes = form["image"].file.read()
                layout_id = form["layout_id"].value
            elif ct.startswith("application/json"):
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode())
                payload = body.get("inputs", body)
                image_bytes = payload["image"]  # base64 or bytes
                layout_id = payload["layout_id"]
            else:
                self._json(400, {"error": f"unsupported content-type {ct!r}"})
                return
        except Exception as exc:
            log.exception("request parse failed")
            self._json(400, {"error": f"parse_failed: {exc}"})
            return

        result = HANDLER({"image": image_bytes, "layout_id": str(layout_id).upper()})
        status = 500 if "error" in result and "verdict" not in result else 200
        self._json(status, result)

    # Quieter access logs — one line per request
    def log_message(self, fmt: str, *args) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument(
        "--stage",
        action="store_true",
        help="Stage an HF-style model-repo layout in a tmp dir (default: load directly from repo paths)",
    )
    args = p.parse_args()

    global HANDLER
    if args.stage:
        root = stage_model_repo()
        HANDLER = EndpointHandler(str(root))
    else:
        # EndpointHandler can also load directly from the repo because handler.py
        # sits next to pcb_lib.py once imported via sys.path. We need to point it
        # at the repo so pipeline_cache/ and PCB_USED/ resolve correctly.
        # PCB_USED lives under PCB_DATASET/PCB_USED in this repo; stage a tiny
        # symlink layout in a tmp dir so the handler finds it.
        root = Path(tempfile.mkdtemp(prefix="aifi-dev-"))
        (root / "pipeline_cache").symlink_to(REPO / "pipeline_cache")
        (root / "PCB_USED").symlink_to(REPO / "PCB_DATASET" / "PCB_USED")
        log.info("symlinked model-repo layout at %s", root)
        HANDLER = EndpointHandler(str(root))

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    log.info("serving on http://%s:%d  (POST /api/detect)", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
