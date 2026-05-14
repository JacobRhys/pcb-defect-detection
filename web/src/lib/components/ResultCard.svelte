<script lang="ts">
  import { sampleUrl } from '$lib/samples';
  import { CLASS_LABEL } from '$lib/classes';
  import { hms } from '$lib/format';
  import type { CompletedRun } from '$lib/types';

  interface Props { run: CompletedRun; }
  let { run }: Props = $props();
</script>

<article class="card" title={run.tile.serial}>
  <div class="thumb">
    <img src={sampleUrl(run.tile.sample.file)} alt="" />
    <span class="badge mono" data-verdict={run.response.verdict}>{run.response.verdict}</span>
  </div>
  <div class="meta mono">
    <span class="serial">{run.tile.serial}</span>
    <span class="muted">{hms(run.finished_at)}</span>
  </div>
  <div class="summary">
    {#if run.response.boxes.length === 0}
      <span class="muted">clean</span>
    {:else}
      {#each Array.from(new Set(run.response.boxes.map((b) => b.class))) as cls}
        <span class="chip" style="--c: var(--c-{cls.replace('_', '-')})">{CLASS_LABEL[cls]}</span>
      {/each}
    {/if}
  </div>
</article>

<style>
  .card {
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 132px;
    padding: 8px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    flex-shrink: 0;
  }
  .thumb {
    position: relative;
    aspect-ratio: 1.4 / 1;
    overflow: hidden;
    border-radius: var(--r-sm);
    background: #000;
  }
  .thumb img { width: 100%; height: 100%; object-fit: cover; }
  .badge {
    position: absolute;
    top: 4px;
    right: 4px;
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 2px;
    letter-spacing: 0.06em;
  }
  .badge[data-verdict='PASS'] { background: rgba(43,209,126,0.18); color: var(--accent-safe); }
  .badge[data-verdict='FAIL'] { background: rgba(229,72,77,0.18); color: var(--accent-fail); }
  .meta { display: flex; justify-content: space-between; font-size: 10px; }
  .summary { display: flex; flex-wrap: wrap; gap: 3px; font-size: 10px; }
  .chip {
    padding: 1px 6px;
    border-radius: 999px;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--c);
    color: var(--c);
  }
</style>
