<script lang="ts">
  import { sampleUrl } from '$lib/samples';
  import type { QueueTile } from '$lib/types';
  import { hms } from '$lib/format';

  interface Props {
    tile: QueueTile;
    onDragStart?: (e: DragEvent, tile: QueueTile) => void;
    onActivate?: (tile: QueueTile) => void;
  }
  let { tile, onDragStart, onActivate }: Props = $props();
</script>

<button
  class="tile"
  draggable="true"
  ondragstart={(e) => onDragStart?.(e, tile)}
  onclick={() => onActivate?.(tile)}
  aria-label={`Board ${tile.serial}`}
  title="Drag to inspection bay, or click to scan"
>
  <div class="thumb">
    <img src={sampleUrl(tile.sample.file)} alt="" draggable="false" />
    <span class="layout mono">{tile.sample.layout_id}</span>
  </div>
  <div class="meta mono">
    <span class="serial">{tile.serial}</span>
    <span class="muted">{hms(tile.arrived_at)}</span>
  </div>
</button>

<style>
  .tile {
    display: flex;
    flex-direction: column;
    padding: 8px;
    gap: 6px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    text-align: left;
    width: 100%;
    height: 100%;
    min-width: 0;
    overflow: hidden;
    transition: transform 120ms ease, border-color 120ms ease, background 120ms ease;
    cursor: grab;
  }
  .tile:hover {
    transform: scale(1.02);
    border-color: var(--accent-data);
    background: var(--surface-2);
  }
  .tile:active { cursor: grabbing; }
  .thumb {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow: hidden;
    border-radius: var(--r-sm);
    background: var(--surface-2);
  }
  .thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    pointer-events: none;
  }
  .layout {
    position: absolute;
    top: 4px;
    left: 4px;
    background: rgba(14, 17, 22, 0.78);
    color: var(--text);
    font-size: var(--fs-xs);
    padding: 1px 6px;
    border-radius: 2px;
    letter-spacing: 0.04em;
  }
  .meta {
    display: flex;
    justify-content: space-between;
    font-size: var(--fs-sm);
    align-items: center;
  }
  .serial { color: var(--text); }
  .muted { color: var(--text-muted); }
</style>
