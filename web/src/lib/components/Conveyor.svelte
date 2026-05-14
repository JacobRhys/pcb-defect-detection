<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { fly, fade } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';

  import ConveyorTile from './ConveyorTile.svelte';
  import { loadSamples } from '$lib/samples';
  import { makeTile, pushTile, queue } from '$lib/state';
  import type { QueueTile, SampleEntry } from '$lib/types';

  interface Props {
    onDragStart?: (e: DragEvent, tile: QueueTile) => void;
    onActivate?: (tile: QueueTile) => void;
  }
  let { onDragStart, onActivate }: Props = $props();

  let samples = $state<SampleEntry[]>([]);
  let timer: ReturnType<typeof setTimeout> | undefined;

  function scheduleNext() {
    // 2.0 s ± 100 ms jitter per the design spec
    const delay = 2000 + (Math.random() * 200 - 100);
    timer = setTimeout(spawn, delay);
  }

  function spawn() {
    if (samples.length === 0) {
      scheduleNext();
      return;
    }
    const pick = samples[Math.floor(Math.random() * samples.length)];
    pushTile(makeTile(pick));
    scheduleNext();
  }

  onMount(async () => {
    samples = await loadSamples();
    // Prime the queue with a single tile so the bay can take it immediately
    // in AUTOMATIC mode without waiting 2 s for the first spawn.
    if (samples.length > 0) pushTile(makeTile(samples[Math.floor(Math.random() * samples.length)]));
    scheduleNext();
  });

  onDestroy(() => {
    if (timer) clearTimeout(timer);
  });
</script>

<aside class="conveyor" aria-label="Incoming boards">
  <header>
    <span class="title mono">INCOMING</span>
    <span class="count mono muted">{$queue.length}/8</span>
  </header>

  <div class="rail">
    <div class="chevrons" aria-hidden="true"></div>
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
    padding: 12px 14px;
    border-bottom: 1px solid var(--line);
    background: var(--surface-2);
  }
  .title {
    font-size: 11px;
    letter-spacing: 0.16em;
    color: var(--accent-data);
  }
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
