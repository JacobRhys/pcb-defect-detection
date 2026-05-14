import { get } from 'svelte/store';
import { detect, RateLimitedError, warmupPing } from './api';
import { fetchSampleBlob } from './samples';
import { bay, node, recordResult } from './state';
import type { DetectResponse, QueueTile } from './types';

/** Inflight inspection — guards against concurrent bay claims. */
let busy = false;

export function isBusy(): boolean {
  return busy;
}

/**
 * Drive the inspection bay through warming → scanning → result/error for a
 * single tile. Resolves once the bay has settled (result or error).
 */
export async function runInspection(tile: QueueTile): Promise<void> {
  if (busy) {
    // Caller is expected to check isBusy(); ignore overlapping requests.
    return;
  }
  busy = true;
  try {
    bay.set({ kind: 'scanning', tile, started_at: Date.now() });
    const blob = await fetchSampleBlob(tile.sample.file);

    const response: DetectResponse = await detect(blob, tile.sample.layout_id, {
      onColdStart: (eta_ms) => {
        node.set('COLD');
        bay.set({ kind: 'warming', eta_ms, started_at: Date.now() });
      }
    });

    node.set('WARM');
    bay.set({ kind: 'result', tile, response });
    recordResult(tile, response);
  } catch (err) {
    console.error('[aifi/orchestrator] inspection failed for', tile.serial, err);
    let message = 'INSPECTION NODE UNREACHABLE — RETRYING';
    if (err instanceof RateLimitedError) {
      message = `RATE LIMITED — RETRY IN ${err.retry_after_s}s`;
    } else if (err instanceof Error) {
      message = err.message.slice(0, 120);
    }
    bay.set({ kind: 'error', tile, message, attempt: 1 });
  } finally {
    busy = false;
  }
}

let warmupFired = false;

/** Fire-and-forget warmup ping on page load. Idempotent — safe to call twice. */
export function fireWarmupOnce(): void {
  if (warmupFired) return;
  warmupFired = true;
  // The warmup is via HEAD /api/detect — the Pages Function bumps the HF
  // endpoint awake. We update the node store optimistically while waiting.
  if (get(node) === 'UNKNOWN') node.set('COLD');
  warmupPing().finally(() => {
    // After a successful HEAD we still don't know for sure the HF backend is
    // warm — only the next POST 200 confirms it. Leave node=COLD until then.
  });
}
