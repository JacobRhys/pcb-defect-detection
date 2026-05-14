/**
 * Cloudflare Pages Function: /api/detect
 *
 * Browser → this function → Hugging Face Inference Endpoint.
 * The browser MUST NOT see HF_TOKEN; that lives in Pages env. CORS is
 * sidestepped because the browser only talks to the same origin.
 *
 * Env vars (all configurable from the Pages project settings):
 *   HF_TOKEN              — bearer token, READ-only scope on the endpoint
 *   HF_ENDPOINT_URL       — full URL of the HF inference endpoint
 *   DAILY_REQUEST_CAP     — global daily POST cap (default "5000")
 *   MAX_REQUEST_BYTES     — request body limit in bytes (default "10485760" = 10 MB)
 *
 * KV namespaces (bound from Pages project settings → Functions → KV):
 *   DAILY_COUNTER         — used by the global daily-cap counter
 *
 * Per-IP rate limiting is configured on the Cloudflare zone via a built-in
 * rate-limit rule (see DEPLOY.md). This function only enforces the global
 * daily cap and the request-size limit.
 */

export interface Env {
  HF_TOKEN: string;
  HF_ENDPOINT_URL: string;
  DAILY_REQUEST_CAP?: string;
  MAX_REQUEST_BYTES?: string;
  DAILY_COUNTER?: KVNamespace;
}

interface KVNamespace {
  get(key: string): Promise<string | null>;
  put(key: string, value: string, opts?: { expirationTtl?: number }): Promise<void>;
}

const DEFAULT_DAILY_CAP = 5000;
const DEFAULT_MAX_BYTES = 10 * 1024 * 1024;
const HF_TIMEOUT_MS = 30_000;

interface RequestContext {
  request: Request;
  env: Env;
  waitUntil(p: Promise<unknown>): void;
}

/** Warmup ping. Fires a HEAD at the HF endpoint so it spins up while the
 *  user reads the page. We deliberately do not block on the response. */
export const onRequestHead = async ({ request, env }: RequestContext): Promise<Response> => {
  void request;
  if (!env.HF_ENDPOINT_URL || !env.HF_TOKEN) {
    return new Response(null, { status: 503 });
  }
  try {
    const ctrl = new AbortController();
    setTimeout(() => ctrl.abort(), 5000);
    await fetch(env.HF_ENDPOINT_URL, {
      method: 'GET',
      headers: { authorization: `Bearer ${env.HF_TOKEN}` },
      signal: ctrl.signal
    });
  } catch {
    // best-effort warmup; the next POST will report cold-start properly
  }
  return new Response(null, { status: 204 });
};

export const onRequestPost = async (ctx: RequestContext): Promise<Response> => {
  const { request, env } = ctx;

  // 1. Config + secret check
  if (!env.HF_ENDPOINT_URL || !env.HF_TOKEN) {
    return jsonResponse({ error: 'endpoint not configured' }, 500);
  }
  const dailyCap = parseInt(env.DAILY_REQUEST_CAP ?? '', 10) || DEFAULT_DAILY_CAP;
  const maxBytes = parseInt(env.MAX_REQUEST_BYTES ?? '', 10) || DEFAULT_MAX_BYTES;

  // 2. Body size cap (cheap rejection before pinging HF)
  const lenHeader = request.headers.get('content-length');
  if (lenHeader && parseInt(lenHeader, 10) > maxBytes) {
    return jsonResponse({ error: `request exceeds ${maxBytes} bytes` }, 413);
  }

  // 3. Global daily cap via KV counter
  if (env.DAILY_COUNTER) {
    const key = `daily:${todayKey()}`;
    const current = parseInt((await env.DAILY_COUNTER.get(key)) ?? '0', 10);
    if (current >= dailyCap) {
      return jsonResponse(
        { rate_limited: true, retry_after_s: secondsUntilMidnightUTC() },
        429
      );
    }
    // Increment fire-and-forget; KV is eventually consistent — accept some slop.
    ctx.waitUntil(
      env.DAILY_COUNTER.put(key, String(current + 1), { expirationTtl: 60 * 60 * 36 })
    );
  }

  // 4. Forward multipart body. Re-package as JSON for the HF handler, which
  //    expects {"image": <base64>, "layout_id": ...}.
  let payload: { image: string; layout_id: string };
  try {
    payload = await marshalRequest(request, maxBytes);
  } catch (err) {
    return jsonResponse({ error: err instanceof Error ? err.message : 'bad request' }, 400);
  }

  // 5. Forward to HF with timeout
  const ctrl = new AbortController();
  const timeoutId = setTimeout(() => ctrl.abort(), HF_TIMEOUT_MS);
  let upstream: Response;
  try {
    upstream = await fetch(env.HF_ENDPOINT_URL, {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.HF_TOKEN}`,
        'content-type': 'application/json',
        accept: 'application/json'
      },
      body: JSON.stringify({ inputs: payload }),
      signal: ctrl.signal
    });
  } catch (err) {
    return jsonResponse(
      { error: err instanceof Error ? `upstream_unreachable: ${err.message}` : 'upstream_unreachable' },
      502
    );
  } finally {
    clearTimeout(timeoutId);
  }

  // 6. Cold-start: HF returns 503 with x-compute-time / loading info. Surface
  //    a structured cold_start body the client knows how to render.
  if (upstream.status === 503) {
    const eta = parseInt(upstream.headers.get('x-compute-time') ?? '', 10);
    return jsonResponse(
      { cold_start: true, eta_ms: Number.isFinite(eta) && eta > 0 ? eta * 1000 : 20000 },
      503
    );
  }

  // 7. Stream the upstream JSON response back as-is.
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      'content-type': upstream.headers.get('content-type') ?? 'application/json',
      'cache-control': 'no-store'
    }
  });
};

/** Fallback for any other method (GET / DELETE / etc). */
export const onRequest = async ({ request }: RequestContext): Promise<Response> => {
  return jsonResponse({ error: `method ${request.method} not allowed` }, 405);
};

// ---------------------------------------------------------------------------

async function marshalRequest(request: Request, maxBytes: number): Promise<{ image: string; layout_id: string }> {
  const ct = request.headers.get('content-type') ?? '';
  if (!ct.startsWith('multipart/form-data')) {
    throw new Error('expected multipart/form-data');
  }
  const form = await request.formData();
  const layoutRaw = form.get('layout_id');
  const imgRaw = form.get('image');
  if (typeof layoutRaw !== 'string' || !layoutRaw) throw new Error('missing layout_id');
  if (!(imgRaw instanceof Blob)) throw new Error('missing image');
  if (imgRaw.size > maxBytes) throw new Error(`image exceeds ${maxBytes} bytes`);

  const buf = await imgRaw.arrayBuffer();
  return { image: bytesToBase64(new Uint8Array(buf)), layout_id: layoutRaw };
}

function bytesToBase64(bytes: Uint8Array): string {
  // btoa requires a binary string; chunk to avoid stack overflow on big blobs.
  let bin = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(bin);
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' }
  });
}

function todayKey(): string {
  return new Date().toISOString().slice(0, 10);
}

function secondsUntilMidnightUTC(): number {
  const now = new Date();
  const mid = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1));
  return Math.max(1, Math.round((mid.getTime() - now.getTime()) / 1000));
}
