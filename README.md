# PCB defect detection — reference-aware pipeline

A two-stage detector for PCB manufacturing defects (missing hole, mouse bite, open circuit, short, spur, spurious copper) that exploits the fact that a defect-free reference image is available for every PCB layout.

## How it works

1. **Register** the flawed image to its clean reference via ORB + RANSAC homography.
2. **Stage A — proposals**: CLAHE-normalised, per-channel RGB diff between registered flaw and clean → threshold → connected components. Tuned for high recall.
3. **Stage B — classify**: a 6-channel ResNet18 (flaw RGB ⊕ clean RGB) classifies each proposal into `{none, missing_hole, mouse_bite, open_circuit, short, spur, spurious_copper}`.

Validation is by **layout ID** (train: 01, 04–09; val: 10, 11, 12), so the network never sees the same PCB layout twice.

## Results on held-out val layouts (152 images, 768 boxes)

| metric | value |
|---|---|
| GT boxes detected | 766 / 768 |
| False positives | 8 |
| Micro F1 | 0.99 |
| Stage A recall | 99.7% |
| Latency | 544 ms / image (CPU+MPS) |

## Layout

| file | purpose |
|---|---|
| [pcb_lib.py](pcb_lib.py) | Shared helpers — registration, proposals, model, `detect()` |
| [pcb_pipeline.ipynb](pcb_pipeline.ipynb) | End-to-end training pipeline (builds crop cache, trains classifier) |
| [benchmark.ipynb](benchmark.ipynb) | Loads cached model, reports metrics, **interactive viewer** for picking specific images |
| [visualise_defect.ipynb](visualise_defect.ipynb) | Quick clean-vs-flawed side-by-side viewer with bounding boxes |
| `results/` | Earlier classification experiments (ResNet18 / ViT-tiny weights and figures) |

## Setup

```bash
# Python 3.11 environment with torch, torchvision, opencv-python, scikit-learn,
# scikit-image, matplotlib, tqdm, ipywidgets, pillow.
```

Place the PCB dataset at `PCB_DATASET/` with this structure (not included in repo — ~1.9 GB):

```
PCB_DATASET/
├── Annotations/<flaw_type>/<layout>_<flaw>_<idx>.xml
├── images/<flaw_type>/<layout>_<flaw>_<idx>.jpg
└── PCB_USED/<layout>.JPG
```

## Reproducing

1. Run [pcb_pipeline.ipynb](pcb_pipeline.ipynb) top-to-bottom (5–10 min on Apple Silicon MPS). Writes `pipeline_cache/patch_classifier.pt`.
2. Run [benchmark.ipynb](benchmark.ipynb) for the per-class metrics table and the interactive viewer.
