import type {
  ApiResponse,
  ColdStartResponse,
  DetectResponse,
  RateLimitedResponse
} from './types';

const DETECT_PATH = '/api/detect';

export class ColdStartError extends Error {
  eta_ms: number;
  constructor(eta_ms: number) {
    super(`cold start: ${eta_ms} ms`);
    this.eta_ms = eta_ms;
  }
}

export class RateLimitedError extends Error {
  retry_after_s: number;
  constructor(retry_after_s: number) {
    super(`rate limited: retry in ${retry_after_s} s`);
    this.retry_after_s = retry_after_s;
  }
}

function isColdStart(x: ApiResponse): x is ColdStartResponse {
  return 'cold_start' in x && x.cold_start === true;
}
function isRateLimited(x: ApiResponse): x is RateLimitedResponse {
  return 'rate_limited' in x && x.rate_limited === true;
}
function isDetectResponse(x: ApiResponse): x is DetectResponse {
  return 'verdict' in x && 'boxes' in x;
}

/**
 * Fire a HEAD against the detect endpoint so the Pages Function forwards a
 * warmup ping to the HF endpoint while the user reads the page. Response is
 * intentionally ignored — the side effect is the spin-up.
 */
export async function warmupPing(): Promise<void> {
  try {
    await fetch(DETECT_PATH, { method: 'HEAD' });
  } catch {
    // network is the user's problem, not ours
  }
}

/**
 * POST an image + layout_id to /api/detect, with exponential-backoff retries
 * on transient (5xx, network) errors and on cold-start 503s. Cold-start is
 * surfaced via the optional onColdStart callback so the UI can render the
 * warming state with the real ETA.
 */
export async function detect(
  image: Blob,
  layout_id: string,
  opts: {
    onColdStart?: (eta_ms: number) => void;
    maxAttempts?: number;
    signal?: AbortSignal;
  } = {}
): Promise<DetectResponse> {
  const maxAttempts = opts.maxAttempts ?? 3;
  let lastErr: unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const fd = new FormData();
      fd.append('image', image, 'board.jpg');
      fd.append('layout_id', layout_id);
      const res = await fetch(DETECT_PATH, { method: 'POST', body: fd, signal: opts.signal });

      // 503 with a cold_start body is not a hard failure — it's the warming signal.
      if (res.status === 503) {
        const body = (await res.json().catch(() => ({}))) as Partial<ColdStartResponse>;
        const eta = body.eta_ms ?? 20000;
        opts.onColdStart?.(eta);
        await sleep(Math.min(eta, 5000));
        continue;
      }
      if (res.status === 429) {
        const body = (await res.json().catch(() => ({}))) as Partial<RateLimitedResponse>;
        throw new RateLimitedError(body.retry_after_s ?? 60);
      }
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
      }

      const body = (await res.json()) as ApiResponse;
      if (isColdStart(body)) {
        opts.onColdStart?.(body.eta_ms);
        await sleep(Math.min(body.eta_ms, 5000));
        continue;
      }
      if (isRateLimited(body)) throw new RateLimitedError(body.retry_after_s);
      if (!isDetectResponse(body)) throw new Error('malformed response: ' + JSON.stringify(body).slice(0, 200));
      return body;
    } catch (err) {
      lastErr = err;
      if (err instanceof RateLimitedError) throw err;
      if (attempt < maxAttempts) {
        await sleep(1000 * 2 ** (attempt - 1)); // 1s, 2s, 4s
        continue;
      }
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error('detect failed after retries');
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
