<script lang="ts">
  import '../app.css';

  import Conveyor from '$lib/components/Conveyor.svelte';
  import InspectionBay from '$lib/components/InspectionBay.svelte';
  import Telemetry from '$lib/components/Telemetry.svelte';

  import { popTile } from '$lib/state';
  import { isBusy, runInspection } from '$lib/orchestrator';
  import type { QueueTile } from '$lib/types';

  function onTileDragStart(e: DragEvent, tile: QueueTile) {
    if (!e.dataTransfer) return;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/x-tile-id', tile.id);
  }

  /**
   * MANUAL fallback for touch / pointer-only inputs: clicking a tile claims
   * it directly. AUTOMATIC mode's interval claim is unaffected.
   */
  function onTileActivate(tile: QueueTile) {
    if (isBusy()) return;
    const claimed = popTile(tile.id);
    if (claimed) runInspection(claimed);
  }
</script>

<main class="hmi">
  <section class="region conveyor-region">
    <Conveyor onDragStart={onTileDragStart} onActivate={onTileActivate} />
  </section>

  <section class="region bay-region">
    <InspectionBay />
  </section>

  <section class="region telemetry-region">
    <Telemetry />
  </section>
</main>

<style>
  .hmi {
    display: grid;
    grid-template-columns: 20% 60% 20%;
    height: 100vh;
    min-height: 600px;
  }
  .region { min-width: 0; min-height: 0; }

  /* Responsive collapse: stack vertically below 900 px wide.
     Acceptance criterion: usable at 1280×800; stacks gracefully below 900 px. */
  @media (max-width: 900px) {
    .hmi {
      grid-template-columns: 1fr;
      grid-template-rows: 220px minmax(360px, 1fr) auto;
      height: auto;
      min-height: 100vh;
    }
    .telemetry-region { max-height: none; }
  }
</style>
