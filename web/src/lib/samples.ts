import { base } from '$app/paths';
import type { SampleEntry } from './types';

let cache: SampleEntry[] | null = null;

export async function loadSamples(): Promise<SampleEntry[]> {
  if (cache) return cache;
  const res = await fetch(`${base}/samples/manifest.json`, { cache: 'force-cache' });
  if (!res.ok) throw new Error(`failed to load samples manifest: ${res.status}`);
  cache = (await res.json()) as SampleEntry[];
  return cache;
}

export function sampleUrl(file: string): string {
  return `${base}/samples/${file}`;
}

/** Fetch a sample image as a Blob (for posting to /api/detect as FormData). */
export async function fetchSampleBlob(file: string): Promise<Blob> {
  const res = await fetch(sampleUrl(file));
  if (!res.ok) throw new Error(`failed to fetch sample ${file}: ${res.status}`);
  return res.blob();
}
