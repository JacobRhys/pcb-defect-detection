<script lang="ts">
  import type { NodeHealth } from '$lib/types';
  interface Props { state: NodeHealth; }
  let { state }: Props = $props();

  const tone = $derived(
    state === 'WARM' ? 'safe' : state === 'COLD' ? 'warn' : 'muted'
  );
</script>

<div class="ind" data-tone={tone}>
  <span class="led"></span>
  <span class="label mono">NODE</span>
  <span class="state mono">{state}</span>
</div>

<style>
  .ind {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    font-size: var(--fs-sm);
    letter-spacing: 0.12em;
  }
  .led {
    width: 8px; height: 8px; border-radius: 50%;
    animation: blink-1hz 2s linear infinite;
    flex-shrink: 0;
  }
  .label { color: var(--text-muted); font-size: var(--fs-xs); }
  .state { margin-left: auto; }
  .ind[data-tone='safe'] .led { background: var(--accent-safe); animation: none; }
  .ind[data-tone='safe'] .state { color: var(--accent-safe); }
  .ind[data-tone='warn'] .led { background: var(--accent-warn); }
  .ind[data-tone='warn'] .state { color: var(--accent-warn); }
  .ind[data-tone='muted'] .led { background: var(--text-muted); }
  .ind[data-tone='muted'] .state { color: var(--text-muted); }
</style>
