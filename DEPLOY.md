# Deploy runbook

End-to-end setup for the web demo:

1. **HF model repo** — code in this GitHub repo, weights and clean references uploaded manually once
2. **HF Inference Endpoint** — runs `service/handler.py` against `pcb_lib.detect()`
3. **Cloudflare Pages** — builds `/web` and serves it + the `/api/detect` Pages Function

Steady-state operating cost is near zero: HF scale-to-zero, Pages free tier,
Cloudflare's per-IP rate limit + a KV-counter daily cap.

---

## 1. HF model repo — first-time seeding (manual)

Weights (`pipeline_cache/patch_classifier.pt`, ~45 MB) and clean references
(`PCB_DATASET/PCB_USED/`, ~38 MB) are gitignored and therefore NOT available
to GitHub Actions. They are pushed to the HF model repo manually, once, by
a developer with access to the local files. After this, CI keeps the code
(`pcb_lib.py`, `service/handler.py`, `service/requirements.txt`) in sync.

```bash
# Prereqs
pip install huggingface_hub
huggingface-cli login        # paste a WRITE-scope token

# Create the repo (or use the web UI)
huggingface-cli repo create aifi-pcb --type model

# Push code
huggingface-cli upload your-org/aifi-pcb pcb_lib.py
huggingface-cli upload your-org/aifi-pcb service/handler.py        handler.py
huggingface-cli upload your-org/aifi-pcb service/requirements.txt  requirements.txt

# Push weights and clean references via Git LFS (one-time)
git clone https://huggingface.co/your-org/aifi-pcb /tmp/hf-repo
cd /tmp/hf-repo
git lfs install
git lfs track "*.pt" "*.JPG"
mkdir -p pipeline_cache PCB_USED
cp /path/to/AIFI_group/pipeline_cache/patch_classifier.pt pipeline_cache/
cp /path/to/AIFI_group/PCB_DATASET/PCB_USED/*.JPG          PCB_USED/
git add .gitattributes pipeline_cache/ PCB_USED/
git commit -m "seed: weights + clean references"
git push
```

Once seeded, the GitHub Actions workflow `.github/workflows/model.yml` keeps
`pcb_lib.py`, `handler.py`, and `requirements.txt` in sync on every push to
`main`. It does **not** touch the LFS-tracked files.

To re-train and re-seed weights later, repeat the manual push step. Do not
expect CI to do it.

## 2. Hugging Face Inference Endpoint

1. https://ui.endpoints.huggingface.co → New endpoint → pick the `aifi-pcb` model repo.
2. Framework: **Custom (handler.py)**.
3. Hardware: **CPU · smallest tier** (Intel Xeon, 1× vCPU, ~2 GB RAM is enough).
4. **Scaling**:
   - Scale-to-zero: **enabled**
   - Min replicas: **0**
   - Max replicas: **1**
   - Region: closest to the expected demo audience.
5. **Billing**: account-level monthly spend cap, default **$10** (Settings →
   Billing → Spending threshold). Document the cap in your team's deploy
   notes — first-time cold starts and demo bursts can chew through it.
6. After deploy, hit the endpoint URL once with a curl to verify:
   ```bash
   curl -X POST "$HF_ENDPOINT_URL" \
        -H "Authorization: Bearer $HF_TOKEN" \
        -H "Content-Type: application/json" \
        --data '{"inputs": {"image": "'"$(base64 -i some.jpg)"'", "layout_id": "L10"}}'
   ```
   Expect a JSON `{verdict, boxes, timing_ms}` body.

Capture two values for the next step:

- `HF_ENDPOINT_URL` — full URL shown on the endpoint detail page
- `HF_TOKEN` — a **read-only** access token (Settings → Access tokens)

## 3. Cloudflare Pages

1. Cloudflare dashboard → Workers & Pages → Create application → Pages → Connect to GitHub.
2. Select the `AIFI_group` repo, branch `main`.
3. Build configuration:
   - Framework preset: **SvelteKit**
   - Build command: `npm run build`
   - Build output directory: `build`
   - Root directory: `web`
   - Node version: `20`
4. Environment variables (Production):
   - `HF_TOKEN`         = the read-only token from step 2
   - `HF_ENDPOINT_URL`  = the endpoint URL from step 2
   - `DAILY_REQUEST_CAP` (optional) = `5000`
   - `MAX_REQUEST_BYTES` (optional) = `3145728`
5. **KV** binding (Settings → Functions → KV namespace bindings):
   - Variable name: `DAILY_COUNTER`
   - KV namespace: create one called e.g. `aifi_daily_counter`
6. **Per-IP rate limit** (zone-level, Security → WAF → Rate limiting rules):
   - Path matches `/api/detect`
   - Threshold: `30 requests per 5 min per IP`
   - Action: Block, 60 s timeout
7. Push to `main` → Pages auto-builds and deploys.

Verify HF_TOKEN is server-side only: open the deployed URL, DevTools →
Network → trigger a board → confirm the request goes to `/api/detect` on
your Pages origin and the response has no `Authorization` header echoed.

## 4. Secrets and tokens

| Secret           | Where                              | Scope       | Used by                       |
| ---------------- | ---------------------------------- | ----------- | ----------------------------- |
| `HF_TOKEN`       | Cloudflare Pages env (Production)  | read-only   | `web/functions/api/detect.ts` |
| `HF_WRITE_TOKEN` | GitHub Actions secret (this repo)  | write       | `.github/workflows/model.yml` |
| `HF_MODEL_REPO`  | GitHub Actions variable            | n/a         | `.github/workflows/model.yml` |

**Rotation**: rotate both HF tokens quarterly. Update Cloudflare Pages env
in the dashboard (no redeploy needed for env-only changes — Pages picks them
up on the next request). Update GitHub Actions secret in repo settings.

## 5. Lifting the spend cap

If you outgrow the default $10 HF cap (visible spike in the Pages telemetry's
LATENCY KPI flatlining at the 30 s function timeout, or 503s with no
`x-compute-time`):

1. HF account → Billing → raise the spending threshold.
2. Raise `DAILY_REQUEST_CAP` in Pages env if the cap is hit before the
   spend cap.
3. Consider GPU tier or `max replicas = 2` only after confirming the
   workload genuinely justifies it. Default to staying CPU + 1 replica.

## 6. Sample images

`web/public/samples/` is committed. To re-curate (e.g. different layouts):

```bash
python scripts/build_web_samples.py
git add web/public/samples
git commit -m "samples: re-curate demo PCBs"
```

The script is developer-only and depends on `PCB_DATASET/` being present
locally; the web app never reads it at runtime.
