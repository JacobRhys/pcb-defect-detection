<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { fly, fade } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';

  import ConveyorTile from './ConveyorTile.svelte';
  import { loadSamples } from '$lib/samples';
  import { lineActive, makeTile, pushTile, queue } from '$lib/state';
  import type { QueueTile, SampleEntry } from '$lib/types';

  interface Props {
    onDragStart?: (e: DragEvent, tile: QueueTile) => void;
    onActivate?: (tile: QueueTile) => void;
  }
  let { onDragStart, onActivate }: Props = $props();

  let samples = $state<SampleEntry[]>([]);
  let timer: ReturnType<typeof setTimeout> | undefined;
  let lineUnsub: (() => void) | undefined;

  // Shuffled deck: cycle through all samples before repeating any.
  let deck: SampleEntry[] = [];
  let deckIdx = 0;

  function fisherYates(arr: SampleEntry[]): SampleEntry[] {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function nextSample(): SampleEntry {
    if (deckIdx >= deck.length) {
      deck = fisherYates(samples);
      deckIdx = 0;
    }
    return deck[deckIdx++];
  }

  function scheduleNext() {
    // 2.0 s ± 100 ms jitter per the design spec
    const delay = 2000 + (Math.random() * 200 - 100);
    timer = setTimeout(spawn, delay);
  }

  function spawn() {
    if (samples.length === 0 || !get(lineActive)) return;
    pushTile(makeTile(nextSample()));
    scheduleNext();
  }

  onMount(async () => {
    samples = await loadSamples();
    // Prime the queue with a single tile so the bay can take it immediately
    // in AUTOMATIC mode without waiting 2 s for the first spawn.
    if (samples.length > 0) pushTile(makeTile(nextSample()));
    scheduleNext();

    // React to line halt/resume: stop the timer when halted, restart when resumed.
    lineUnsub = lineActive.subscribe((active) => {
      if (!active) {
        if (timer) { clearTimeout(timer); timer = undefined; }
      } else if (!timer) {
        scheduleNext();
      }
    });
  });

  onDestroy(() => {
    if (timer) clearTimeout(timer);
    lineUnsub?.();
  });
</script>

<aside class="conveyor" aria-label="Incoming boards">
  <header class:halted={!$lineActive}>
    <span class="title mono">{$lineActive ? 'INCOMING' : 'LINE HALTED'}</span>
    <span class="count mono muted">{$lineActive ? `${$queue.length}/8` : '—'}</span>
  </header>

  <div class="rail">
    <div class="chevrons" class:paused={!$lineActive} aria-hidden="true"></div>
    <ul class="tiles">
      {#each $queue as tile (tile.id)}
        <li
          in:fly={{ y: -24, duration: 200, easing: quintOut }}
          out:fade={{ duration: 180 }}
        >
          <ConveyorTile {tile} {onDragStart} {onActivate} />
        </li>
      {/each}
    </ul>
  </div>
</aside>

<style>
  .conveyor {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--surface);
    border-right: 1px solid var(--line);
    min-width: 0;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 44px;
    padding: 0 14px;
    border-bottom: 1px solid var(--line);
    background: var(--surface-2);
    font-size: 11px;
  }
  .title {
    font-size: 11px;
    letter-spacing: 0.16em;
    color: var(--accent-data);
    transition: color 200ms ease;
  }
  header.halted .title { color: var(--accent-warn); }
  .count { font-size: 11px; }
  .rail {
    position: relative;
    flex: 1;
    overflow: hidden;
    padding: 10px;
  }
  .chevrons {
    position: absolute;
    inset: 0;
    background-image: repeating-linear-gradient(
      90deg,
      transparent 0,
      transparent 10px,
      rgba(62, 166, 255, 0.05) 10px,
      rgba(62, 166, 255, 0.05) 12px,
      transparent 12px,
      transparent 24px
    );
    animation: chevron 1s linear infinite;
    opacity: 0.6;
    pointer-events: none;
    transition: opacity 400ms ease;
  }
  .chevrons.paused {
    animation-play-state: paused;
    opacity: 0.12;
  }
  .tiles {
    position: relative;
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
</style>
