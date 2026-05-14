import { derived, get, writable, type Readable, type Writable } from 'svelte/store';
import type {
  BayState,
  CompletedRun,
  ConveyorMode,
  DefectClass,
  DetectResponse,
  NodeHealth,
  QueueTile,
  SampleEntry
} from './types';
import { DEFECT_CLASSES } from './classes';
import { makeSerial, uuid } from './format';

const QUEUE_CAP = 8;
const COMPLETED_CAP = 5;
const LOG_CAP = 100;
const LATENCY_WINDOW = 50;
const AVG_LATENCY_WINDOW = 20;

export const mode: Writable<ConveyorMode> = writable('AUTOMATIC');
export const queue: Writable<QueueTile[]> = writable([]);
export const bay: Writable<BayState> = writable({ kind: 'idle' });
export const completed: Writable<CompletedRun[]> = writable([]);
export const node: Writable<NodeHealth> = writable('UNKNOWN');

// Telemetry-side stores
export interface LogRow {
  id: string;
  t: number;
  serial: string;
  verdict: 'PASS' | 'FAIL';
  summary: string;
}
export const logRows: Writable<LogRow[]> = writable([]);

/** Latency samples (ms total). Bounded ring. */
export const latencyHistory: Writable<number[]> = writable([]);
/** Run-finish timestamps for throughput. */
export const runTimestamps: Writable<number[]> = writable([]);
/** Per-class defect counts this session. */
export const defectCounts: Writable<Record<DefectClass, number>> = writable(
  Object.fromEntries(DEFECT_CLASSES.map((c) => [c, 0])) as Record<DefectClass, number>
);
/** Session totals (PASS / FAIL board counts). */
export const sessionTotals: Writable<{ pass: number; fail: number }> = writable({ pass: 0, fail: 0 });

let seq = 0;

export function makeTile(sample: SampleEntry, now: Date = new Date()): QueueTile {
  seq += 1;
  return {
    id: uuid(),
    sample,
    serial: makeSerial(sample.layout_id, seq, now),
    arrived_at: Date.now()
  };
}

/** Push a tile onto the conveyor; older tiles fall off when over QUEUE_CAP. */
export function pushTile(tile: QueueTile): void {
  queue.update((q) => {
    const next = [tile, ...q];
    return next.slice(0, QUEUE_CAP);
  });
}

/** Remove a tile from the queue by id (called when the bay claims it). */
export function popTile(id: string): QueueTile | undefined {
  let removed: QueueTile | undefined;
  queue.update((q) => {
    const idx = q.findIndex((t) => t.id === id);
    if (idx === -1) return q;
    removed = q[idx];
    return [...q.slice(0, idx), ...q.slice(idx + 1)];
  });
  return removed;
}

export function takeOldestQueued(): QueueTile | undefined {
  const q = get(queue);
  if (q.length === 0) return undefined;
  const oldest = q[q.length - 1];
  popTile(oldest.id);
  return oldest;
}

/** Record a finished run: bay rail, telemetry, log. */
export function recordResult(tile: QueueTile, response: DetectResponse): void {
  const finishedAt = Date.now();
  completed.update((c) => [{ id: uuid(), tile, response, finished_at: finishedAt }, ...c].slice(0, COMPLETED_CAP));
  latencyHistory.update((h) => {
    const next = [...h, response.timing_ms.total];
    return next.length > LATENCY_WINDOW ? next.slice(next.length - LATENCY_WINDOW) : next;
  });
  runTimestamps.update((ts) => {
    const cutoff = finishedAt - 120000; // keep 2 min for the 60s rolling KPI
    return [...ts.filter((t) => t >= cutoff), finishedAt];
  });
  sessionTotals.update((s) =>
    response.verdict === 'PASS' ? { ...s, pass: s.pass + 1 } : { ...s, fail: s.fail + 1 }
  );
  if (response.boxes.length) {
    defectCounts.update((d) => {
      const next = { ...d };
      for (const b of response.boxes) next[b.class] = (next[b.class] ?? 0) + 1;
      return next;
    });
  }
  logRows.update((rows) => {
    const summary =
      response.boxes.length === 0
        ? 'clean'
        : summariseBoxes(response);
    return [
      {
        id: uuid(),
        t: finishedAt,
        serial: tile.serial,
        verdict: response.verdict,
        summary
      },
      ...rows
    ].slice(0, LOG_CAP);
  });
}

function summariseBoxes(r: DetectResponse): string {
  const tally: Partial<Record<DefectClass, number>> = {};
  for (const b of r.boxes) tally[b.class] = (tally[b.class] ?? 0) + 1;
  return Object.entries(tally)
    .map(([k, v]) => `${k} ×${v}`)
    .join(', ');
}

/** Derived: throughput in boards/min over a 60 s rolling window. */
export const throughput: Readable<number> = derived(runTimestamps, ($ts) => {
  const now = Date.now();
  const within = $ts.filter((t) => now - t <= 60000).length;
  return within; // already boards in last 60s == boards/min
});

/** Derived: yield % = pass / (pass + fail) over the session. */
export const yieldPct: Readable<number> = derived(sessionTotals, ($s) => {
  const total = $s.pass + $s.fail;
  if (total === 0) return 100;
  return (100 * $s.pass) / total;
});

/** Derived: rolling mean latency over last AVG_LATENCY_WINDOW runs. */
export const avgLatency: Readable<number> = derived(latencyHistory, ($h) => {
  if ($h.length === 0) return 0;
  const win = $h.slice(-AVG_LATENCY_WINDOW);
  return win.reduce((a, b) => a + b, 0) / win.length;
});

/** Derived: total defect count this session. */
export const totalDefects: Readable<number> = derived(defectCounts, ($d) =>
  Object.values($d).reduce((a, b) => a + b, 0)
);

/** Reset the whole session (used by the RESET button). */
export function resetSession(): void {
  queue.set([]);
  bay.set({ kind: 'idle' });
  completed.set([]);
  logRows.set([]);
  latencyHistory.set([]);
  runTimestamps.set([]);
  defectCounts.set(
    Object.fromEntries(DEFECT_CLASSES.map((c) => [c, 0])) as Record<DefectClass, number>
  );
  sessionTotals.set({ pass: 0, fail: 0 });
  seq = 0;
}
