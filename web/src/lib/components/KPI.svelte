<script lang="ts">
  import { onDestroy } from 'svelte';
  import { tween } from '$lib/format';

  interface Props {
    label: string;
    unit: string;
    window: string;
    value: number;
    decimals?: number;
    accent?: string;
  }
  let { label, unit, window, value, decimals = 0, accent }: Props = $props();

  let displayed = $state(0);
  let cancel: (() => void) | undefined;
  let primed = false;

  $effect(() => {
    const target = value;
    if (!primed) {
      displayed = target;
      primed = true;
      return;
    }
    if (cancel) cancel();
    cancel = tween(displayed, target, 400, (v) => (displayed = v));
  });
  onDestroy(() => cancel?.());
</script>

<div class="kpi">
  <div class="head">
    <span class="label mono">{label}</span>
    <span class="window mono muted">{window}</span>
  </div>
  <div class="value">
    <span class="num mono" style:color={accent ?? 'inherit'}>{displayed.toFixed(decimals)}</span>
    <span class="unit mono muted">{unit}</span>
  </div>
</div>

<style>
  .kpi {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 10px 12px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--r-md);
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .label { font-size: var(--fs-xs); letter-spacing: 0.14em; color: var(--text-muted); }
  .window { font-size: var(--fs-2xs); letter-spacing: 0.08em; }
  .value { display: flex; align-items: baseline; gap: 6px; }
  .num { font-size: var(--fs-kpi); font-weight: 600; }
  .unit { font-size: var(--fs-xs); }
</style>
