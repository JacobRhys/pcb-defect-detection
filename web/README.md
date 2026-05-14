# `web/` — PCB Inspection HMI

Single-page SvelteKit app styled as an in-line AOI station HMI. Production
build is a fully static export served by Cloudflare Pages; the only
server-side code is the Pages Function at [`functions/api/detect.ts`](functions/api/detect.ts),
which proxies inference requests to a Hugging Face Inference Endpoint.

## Layout

```
src/
  app.html, app.css, app.d.ts
  routes/
    +layout.ts           (prerender = true, ssr = false)
    +page.svelte         (composes the three HMI regions)
  lib/
    api.ts               (detect() with retry/backoff + cold-start handling)
    classes.ts           (DefectClass -> colour / label)
    format.ts            (serial, hms, tween)
    orchestrator.ts      (runInspection: scanning -> result/error)
    samples.ts           (manifest loader, sample-url helpers)
    state.ts             (Svelte stores: queue, bay, telemetry)
    types.ts             (shared TS types)
    components/
      Conveyor.svelte, ConveyorTile.svelte
      InspectionBay.svelte, ResultCard.svelte
      Telemetry.svelte, KPI.svelte, Sparkline.svelte,
      DefectMix.svelte, LogPanel.svelte, NodeIndicator.svelte

public/
  samples/               (40 demo PCBs + manifest.json, ~1.8 MB)

functions/
  api/detect.ts          (Cloudflare Pages Function proxy)
```

## Local development

```bash
cd web
npm ci
npm run dev          # Vite dev server on :5173
```

Vite proxies `/api/*` to `http://127.0.0.1:8788` — that's where the local
Cloudflare Pages dev server (`wrangler pages dev`) is expected to be running.
To test the proxy locally:

```bash
# in a second terminal, from the repo root
npx wrangler pages dev web/build --port 8788 \
  --binding HF_TOKEN=... \
  --binding HF_ENDPOINT_URL=https://...
# (build first with `npm run build` so /web/build exists)
```

If you only want to develop the frontend without a live endpoint, the cold-
start state + retry/backoff will surface honestly when the proxy is absent;
you'll see `INSPECTION NODE UNREACHABLE — RETRYING` rather than fake data.
The demo intentionally does not ship a mock — every box you see on screen
came from the real pipeline.

## Production build

```bash
npm run build        # static export to web/build/
npm run check        # svelte-check + tsc
```

Cloudflare Pages is configured (in the Pages project settings) with:
- Build command: `npm run build`
- Build output directory: `build`
- Root directory: `web`
- Node version: 20

## Environment variables (set in Pages project settings)

| Var                 | Required | Purpose                                 |
| ------------------- | -------- | --------------------------------------- |
| `HF_TOKEN`          | yes      | Bearer token for the HF endpoint        |
| `HF_ENDPOINT_URL`   | yes      | Full URL of the HF inference endpoint   |
| `DAILY_REQUEST_CAP` | no       | Global daily POST cap (default 5000)    |
| `MAX_REQUEST_BYTES` | no       | Per-request body limit (default 3 MB)   |

Bind a KV namespace called `DAILY_COUNTER` under Functions → KV namespaces
to enable the global daily cap. Without it, the cap is a no-op.

See [`../DEPLOY.md`](../DEPLOY.md) for first-time setup, secret rotation,
and lifting the spend cap.

## Acceptance-criteria mapping

| Criterion                              | Where                                                                  |
| -------------------------------------- | ---------------------------------------------------------------------- |
| Tile every 2.0 s ± 100 ms              | `lib/components/Conveyor.svelte` `scheduleNext()`                      |
| Drop fires real call                   | `routes/+page.svelte` → `lib/orchestrator.ts:runInspection`            |
| Warmup ping on page load               | `lib/orchestrator.ts:fireWarmupOnce` → `lib/api.ts:warmupPing`         |
| Cold-start ETA from 503                | `functions/api/detect.ts:onRequestPost` + `lib/api.ts:detect`          |
| AUTOMATIC/MANUAL toggle preserves queue | `lib/state.ts` (queue store untouched by mode change)                  |
| HF_TOKEN never reaches browser         | Token only read in Pages Function; never imported by `lib/`            |
| Spend cap + rate limit configurable    | `DAILY_REQUEST_CAP` env var + Cloudflare per-IP rule (see DEPLOY.md)   |
| Layout responsive ≤ 900 px              | `routes/+page.svelte` `@media (max-width: 900px)`                      |
