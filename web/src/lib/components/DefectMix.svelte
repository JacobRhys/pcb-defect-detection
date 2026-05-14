<script lang="ts">
  import { CLASS_LABEL, DEFECT_CLASSES } from '$lib/classes';
  import type { DefectClass } from '$lib/types';

  interface Props { counts: Record<DefectClass, number>; }
  let { counts }: Props = $props();

  let total = $derived(Object.values(counts).reduce((a, b) => a + b, 0));
</script>

<div class="mix">
  <div class="bar">
    {#each DEFECT_CLASSES as cls}
      {@const v = counts[cls] ?? 0}
      {#if v > 0}
        <span
          class="seg"
          style="flex: {v}; background: var(--c-{cls.replace('_', '-')})"
          title="{CLASS_LABEL[cls]}: {v}"
        ></span>
      {/if}
    {/each}
    {#if total === 0}
      <span class="seg empty" style="flex: 1"></span>
    {/if}
  </div>
  <ul class="legend mono">
    {#each DEFECT_CLASSES as cls}
      <li>
        <span class="swatch" style="background: var(--c-{cls.replace('_', '-')})"></span>
        <span class="name">{CLASS_LABEL[cls]}</span>
        <span class="count muted">{counts[cls] ?? 0}</span>
      </li>
    {/each}
  </ul>
</div>

<style>
  .mix { display: flex; flex-direction: column; gap: 8px; }
  .bar {
    display: flex;
    height: 10px;
    border-radius: 4px;
    overflow: hidden;
    background: var(--surface-2);
    border: 1px solid var(--line);
  }
  .seg { display: block; }
  .seg.empty { background: transparent; }
  .legend {
    list-style: none;
    padding: 0; margin: 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px 8px;
    font-size: var(--fs-xs);
  }
  .legend li {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }
  .swatch { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }
  .name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .count { flex-shrink: 0; }
</style>
