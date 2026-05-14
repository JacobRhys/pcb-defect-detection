# `service/` — HF Inference Endpoint handler

Custom-container handler that wraps `pcb_lib.detect()` for a Hugging Face
Inference Endpoint. The endpoint is the runtime backing the
[`/web`](../web/) demo.

## Files

| File              | Purpose                                                |
| ----------------- | ------------------------------------------------------ |
| `handler.py`      | `EndpointHandler` — loads weights once, serves JSON.   |
| `requirements.txt`| Pinned to the same versions as the local Python 3.11 dev env (torch 2.5.1, torchvision 0.20.1, opencv-python-headless 4.8.0.76, numpy 1.24.3). |

## Handler contract

```jsonc
// request
{
  "image":     "<bytes or base64 string, <= 2 MB>",
  "layout_id": "L01" | "L04" | ... | "L12"
}
```

```jsonc
// success
{
  "verdict": "PASS" | "FAIL",
  "boxes":   [{ "x": int, "y": int, "w": int, "h": int,
                "class": "missing_hole|mouse_bite|open_circuit|short|spur|spurious_copper",
                "confidence": float }],
  "timing_ms": { "register": int, "propose": int, "classify": int, "total": int }
}
```

```jsonc
// error
{ "error": "..." }
```

The handler does **not** reimplement detection — it imports
`pcb_lib.detect()` from the repo root file. The HF model-repo layout is:

```
<repo>/
  handler.py
  pcb_lib.py                          (copied from GitHub repo root)
  requirements.txt
  pipeline_cache/patch_classifier.pt  (Git LFS)
  PCB_USED/01.JPG ... 12.JPG          (Git LFS — clean references)
```

`handler.py` overrides `pcb_lib.CACHE_DIR` and `pcb_lib.CLEAN_DIR` at
construction so paths resolve relative to itself, which lets the exact
same code run in the HF container and in a local smoke test.

## Local smoke test

```bash
cd service
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Stage a fake model-repo layout in a tmp dir, mirroring HF:
TMP=$(mktemp -d)
cp ../pcb_lib.py handler.py requirements.txt "$TMP/"
mkdir "$TMP/pipeline_cache" "$TMP/PCB_USED"
cp ../pipeline_cache/patch_classifier.pt "$TMP/pipeline_cache/"
cp ../PCB_DATASET/PCB_USED/*.JPG "$TMP/PCB_USED/"

# Pick any flawed image from PCB_DATASET and call the handler:
python handler.py \
  --root "$TMP" \
  --image ../PCB_DATASET/images/short/10_short_01.jpg \
  --layout L10
```

A passing run prints a JSON object with `verdict`, `boxes`, and
`timing_ms`. First call after process start pays a ~2–4 s warmup
inside `EndpointHandler.__init__`; subsequent calls run in ~500 ms on
CPU.

## Deploy

See [`../DEPLOY.md`](../DEPLOY.md) for the HF endpoint creation and
model-repo seeding steps. Weights and `PCB_USED/` are pushed manually
once; CI thereafter only updates `pcb_lib.py`, `handler.py`, and
`requirements.txt`.
