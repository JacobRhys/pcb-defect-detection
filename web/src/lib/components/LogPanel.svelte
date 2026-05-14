<script lang="ts">
  import { fly } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';
  import { hms } from '$lib/format';
  import type { LogRow } from '$lib/state';

  interface Props { rows: LogRow[]; rowCount?: number; }
  let { rows, rowCount = 8 }: Props = $props();
</script>

<div class="log mono">
  {#each rows.slice(0, rowCount) as row (row.id)}
    <div
      class="row"
      data-verdict={row.verdict}
      in:fly={{ y: -10, duration: 160, easing: quintOut }}
    >
      <span class="t">{hms(row.t)}</span>
      <span class="serial">{row.serial}</span>
      <span class="verdict">{row.verdict}</span>
      <span class="summary">{row.summary}</span>
    </div>
  {/each}
  {#if rows.length === 0}
    <div class="row empty muted">— no boards processed —</div>
  {/if}
</div>

<style>
  .log {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 10px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    padding: 6px 8px;
    overflow: hidden;
  }
  .row {
    display: grid;
    grid-template-columns: 56px 1fr 32px 1fr;
    gap: 8px;
    padding: 2px 0;
    align-items: baseline;
    white-space: nowrap;
    overflow: hidden;
  }
  .row.empty {
    display: block;
    text-align: center;
    padding: 6px 0;
  }
  .t { color: var(--text-muted); }
  .serial { overflow: hidden; text-overflow: ellipsis; }
  .verdict { text-align: right; }
  .row[data-verdict='PASS'] .verdict { color: var(--accent-safe); }
  .row[data-verdict='FAIL'] .verdict { color: var(--accent-fail); }
  .summary {
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--text-muted);
  }
</style>
