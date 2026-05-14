/** Generate a lot-code style serial: L{layout}-{YYYYMMDD}-{seq:04d}. */
export function makeSerial(layoutId: string, seq: number, now: Date = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  const s = String(seq % 10000).padStart(4, '0');
  return `${layoutId}-${y}${m}${d}-${s}`;
}

export function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  // Best-effort fallback (older browsers); randomness quality is not security-critical.
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function hms(ms: number): string {
  const d = new Date(ms);
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  const s = String(d.getSeconds()).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

/** Tween a numeric value over `duration` ms using requestAnimationFrame. */
export function tween(from: number, to: number, duration: number, onUpdate: (v: number) => void): () => void {
  const start = performance.now();
  let raf = 0;
  const step = (t: number) => {
    const p = Math.min(1, (t - start) / duration);
    // ease-out cubic
    const eased = 1 - Math.pow(1 - p, 3);
    onUpdate(from + (to - from) * eased);
    if (p < 1) raf = requestAnimationFrame(step);
  };
  raf = requestAnimationFrame(step);
  return () => cancelAnimationFrame(raf);
}
