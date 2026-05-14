<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { fly } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';

  import ResultCard from './ResultCard.svelte';
  import { sampleUrl } from '$lib/samples';
  import { CLASS_LABEL } from '$lib/classes';
  import { bay, completed, lineActive, mode, popTile, resetSession, takeOldestQueued, toggleLine } from '$lib/state';
  import { fireWarmupOnce, isBusy, runInspection } from '$lib/orchestrator';
  import type { ConveyorMode, QueueTile } from '$lib/types';

  // Drop-zone state for visual feedback
  let dropActive = $state(false);

  // Auto-flow timer (AUTOMATIC mode)
  let autoTimer: ReturnType<typeof setInterval> | undefined;

  // Optimistic chip phase clock — ticks until server timing lands
  let phaseTick = $state(0);
  let phaseRaf = 0;

  // Image natural dims for overlay scaling
  let imgEl = $state<HTMLImageElement | null>(null);
  let natural = $state({ w: 0, h: 0 });

  // When mode switches to AUTOMATIC, immediately claim next queued tile
  // rather than waiting up to 4 s for the interval to fire.
  let prevMode: ConveyorMode | undefined;
  const unsubMode = mode.subscribe((m) => {
    if (prevMode !== undefined && prevMode !== m && m === 'AUTOMATIC') {
      if (!isBusy() && $lineActive) {
        const tile = takeOldestQueued();
        if (tile) runInspection(tile);
      }
    }
    prevMode = m;
  });

  onMount(() => {
    fireWarmupOnce();
    autoTimer = setInterval(() => {
      if ($mode !== 'AUTOMATIC') return;
      if (!$lineActive) return;
      if (isBusy()) return;
      const tile = takeOldestQueued();
      if (tile) runInspection(tile);
    }, 4000);
    const loop = (t: number) => {
      phaseTick = t;
      phaseRaf = requestAnimationFrame(loop);
    };
    phaseRaf = requestAnimationFrame(loop);
  });

  onDestroy(() => {
    if (autoTimer) clearInterval(autoTimer);
    cancelAnimationFrame(phaseRaf);
    unsubMode();
  });

  function onDragOver(e: DragEvent) {
    e.preventDefault();
    dropActive = true;
  }
  function onDragLeave() {
    dropActive = false;
  }
  function onDrop(e: DragEvent) {
    e.preventDefault();
    dropActive = false;
    const id = e.dataTransfer?.getData('text/x-tile-id');
    if (!id) return;
    const tile = popTile(id);
    if (tile && !isBusy()) runInspection(tile);
  }

  /**
   * Optimistic phase progress: each chip takes ~targetMs to "complete".
   * Once server timing lands, the chips lock to the reported values.
   */
  const OPT = { register: 600, propose: 400, classify: 900, report: 200 };

  function chipState(elapsed: number, serverTiming: BayResultTimingOrUndef): ChipReadout {
    const t = serverTiming;
    if (t) {
      return {
        register: { ms: t.register, done: true },
        propose: { ms: t.propose, done: true },
        classify: { ms: t.classify, done: true },
        report: { ms: Math.max(0, t.total - (t.register + t.propose + t.classify)), done: true }
      };
    }
    const ticks = phaseTick; // ensure reactivity
    void ticks;
    let rem = elapsed;
    const out: ChipReadout = {
      register: { ms: 0, done: false },
      propose: { ms: 0, done: false },
      classify: { ms: 0, done: false },
      report: { ms: 0, done: false }
    };
    for (const k of ['register', 'propose', 'classify', 'report'] as const) {
      const cap = OPT[k];
      const used = Math.min(rem, cap);
      out[k] = { ms: Math.round(used), done: used >= cap };
      rem -= used;
      if (rem <= 0) break;
    }
    return out;
  }

  type BayResultTimingOrUndef = { register: number; propose: number; classify: number; total: number } | undefined;
  type ChipReadout = Record<'register' | 'propose' | 'classify' | 'report', { ms: number; done: boolean }>;

  function onImgLoad(e: Event) {
    const img = e.currentTarget as HTMLImageElement;
    natural = { w: img.naturalWidth, h: img.naturalHeight };
  }

  function toggleMode() {
    mode.update((m) => (m === 'AUTOMATIC' ? 'MANUAL' : 'AUTOMATIC'));
  }
</script>

<!-- svelte-ignore a11y_no_redundant_roles -->
<section
  class="bay"
  class:drop={dropActive}
  role="region"
  aria-label="Inspection bay — drop a board here to scan"
  ondragover={onDragOver}
  ondragleave={onDragLeave}
  ondrop={onDrop}
>
  <header>
    <div class="status-group">
      <span class="led" data-state={$bay.kind}></span>
      <span class="status mono">{$bay.kind.toUpperCase()}</span>
    </div>
    <div class="controls">
      <button
        class="line-ctrl mono"
        class:running={$lineActive}
        onclick={toggleLine}
        aria-pressed={!$lineActive}
        title={$lineActive ? 'Halt the inspection line' : 'Start the inspection line'}
      >
        <span class="line-dot" data-active={$lineActive}></span>
        {$lineActive ? 'HALT LINE' : 'START LINE'}
      </button>
      <button class="toggle" onclick={toggleMode} aria-pressed={$mode === 'AUTOMATIC'} disabled={!$lineActive}>
        <span class="dot" data-on={$mode === 'AUTOMATIC'}></span>
        {$mode}
      </button>
      <button onclick={resetSession}>RESET</button>
    </div>
  </header>

  <div class="stage dotgrid">
    {#if $bay.kind === 'idle'}
      {#if !$lineActive}
        <div class="overlay-msg line-halted">
          <span class="halt-bars" aria-hidden="true">&#9646;&#9646;</span>
          <p class="awaiting mono">LINE HALTED</p>
          <p class="hint muted">Press START LINE to resume inspection.</p>
        </div>
      {:else}
        <div class="overlay-msg">
          <span class="ring"></span>
          <p class="awaiting mono">AWAITING BOARD</p>
          <p class="hint muted">Drag a tile from the conveyor, or wait for AUTOMATIC mode.</p>
        </div>
      {/if}
    {:else if $bay.kind === 'warming'}
      <div class="overlay-msg">
        <p class="awaiting mono">SPINNING UP INFERENCE NODE</p>
        <p class="hint muted">~{Math.round($bay.eta_ms / 1000)}s on first board of the session.</p>
        <div class="progress"><div class="bar" style="animation-duration: {$bay.eta_ms}ms"></div></div>
      </div>
    {:else if $bay.kind === 'scanning' || $bay.kind === 'result'}
      <div class="board-wrap">
        <img
          bind:this={imgEl}
          src={sampleUrl($bay.tile.sample.file)}
          alt="Board under inspection"
          onload={onImgLoad}
        />
        {#if $bay.kind === 'scanning'}
          <div class="scanline" aria-hidden="true"></div>
        {/if}
        {#if $bay.kind === 'result' && natural.w > 0}
          {@const r = $bay.response}
          {#each r.boxes as box, i (i)}
            <div
              class="bbox"
              style="
                left: {(box.x / natural.w) * 100}%;
                top: {(box.y / natural.h) * 100}%;
                width: {(box.w / natural.w) * 100}%;
                height: {(box.h / natural.h) * 100}%;
                --c: var(--c-{box.class.replace('_', '-')});
              "
            >
              <span class="bbox-label mono">
                {CLASS_LABEL[box.class]} · {(box.confidence * 100).toFixed(0)}%
              </span>
            </div>
          {/each}
        {/if}
      </div>
    {:else if $bay.kind === 'error'}
      <div class="overlay-msg error">
        <p class="awaiting mono">{$bay.message}</p>
      </div>
    {/if}
  </div>

  {#if $bay.kind === 'scanning' || $bay.kind === 'result'}
    {@const elapsed = Date.now() - ($bay.kind === 'scanning' ? $bay.started_at : 0)}
    {@const reads = chipState(elapsed, $bay.kind === 'result' ? $bay.response.timing_ms : undefined)}
    <div class="phases mono">
      {#each ['register', 'propose', 'classify', 'report'] as const as phase}
        {@const r = reads[phase]}
        <div class="chip" class:done={r.done}>
          <span class="label">{phase.toUpperCase()}</span>
          <span class="ms">{r.ms} ms</span>
        </div>
      {/each}
    </div>
  {/if}

  {#if $bay.kind === 'result'}
    <div class="verdict mono" data-verdict={$bay.response.verdict}>
      {$bay.response.verdict === 'PASS' ? 'BOARD PASSED' : `BOARD FAILED · ${$bay.response.boxes.length} DEFECT${$bay.response.boxes.length === 1 ? '' : 'S'}`}
    </div>
  {/if}

  <footer class="completed-rail">
    <span class="rail-label mono muted">LAST 5</span>
    <div class="rail">
      {#each $completed as run (run.id)}
        <div in:fly={{ x: -32, duration: 220, easing: quintOut }}>
          <ResultCard {run} />
        </div>
      {/each}
    </div>
  </footer>
</section>

<style>
  .bay {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg);
    border-right: 1px solid var(--line);
    min-width: 0;
    position: relative;
  }
  .bay.drop {
    outline: 2px dashed var(--accent-data);
    outline-offset: -8px;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 44px;
    padding: 0 14px;
    border-bottom: 1px solid var(--line);
    background: var(--surface-2);
    font-size: var(--fs-sm);
  }
  .status-group { display: flex; align-items: center; gap: 8px; }
  .status { font-size: var(--fs-sm); letter-spacing: 0.14em; }
  .led {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--text-muted);
    animation: blink-1hz 2s linear infinite;
  }
  .led[data-state='scanning'] { background: var(--accent-data); }
  .led[data-state='warming']  { background: var(--accent-warn); }
  .led[data-state='result']   { background: var(--accent-safe); animation: none; }
  .led[data-state='error']    { background: var(--accent-fail); }
  .controls { display: flex; gap: 8px; }
  .toggle { display: flex; align-items: center; gap: 8px; }
  .toggle .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--text-muted);
    transition: background 160ms ease;
  }
  .toggle .dot[data-on='true'] { background: var(--accent-safe); }
  .toggle:disabled { opacity: 0.35; cursor: not-allowed; pointer-events: none; }

  /* HALT / START LINE control */
  .line-ctrl {
    display: flex;
    align-items: center;
    gap: 7px;
    letter-spacing: 0.1em;
    border-color: var(--accent-safe);
    color: var(--accent-safe);
    transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
  }
  .line-ctrl:hover { background: color-mix(in srgb, var(--accent-safe) 10%, transparent); }
  .line-ctrl.running {
    border-color: var(--accent-warn);
    color: var(--accent-warn);
  }
  .line-ctrl.running:hover { background: color-mix(in srgb, var(--accent-warn) 10%, transparent); }
  .line-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--accent-safe);
    transition: background 160ms ease;
    box-shadow: 0 0 0 0 var(--accent-safe);
  }
  .line-dot[data-active='true'] {
    background: var(--accent-warn);
    animation: pulse-warn 2s ease-in-out infinite;
  }
  @keyframes pulse-warn {
    0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent-warn) 60%, transparent); }
    50%       { box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent-warn) 0%, transparent); }
  }

  .stage {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .overlay-msg {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    text-align: center;
  }
  .awaiting {
    letter-spacing: 0.18em;
    color: var(--accent-data);
    animation: blink-1hz 2.4s ease-in-out infinite;
  }
  .overlay-msg.error .awaiting { color: var(--accent-fail); }
  .overlay-msg.line-halted .awaiting {
    color: var(--accent-warn);
    animation: blink-1hz 1.6s ease-in-out infinite;
  }
  .halt-bars {
    font-size: 28px;
    color: var(--accent-warn);
    letter-spacing: 4px;
    opacity: 0.85;
  }
  .hint { font-size: var(--fs-md); max-width: 360px; }
  .ring {
    width: 64px; height: 64px;
    border: 1.5px dashed var(--line);
    border-radius: 50%;
  }
  .progress {
    width: 240px; height: 4px;
    background: var(--surface-2);
    border-radius: 2px; overflow: hidden;
    margin-top: 8px;
  }
  .progress .bar {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-warn), var(--accent-data));
    width: 0;
    animation-name: fill;
    animation-timing-function: linear;
    animation-fill-mode: forwards;
  }
  @keyframes fill { from { width: 0; } to { width: 100%; } }

  .board-wrap {
    position: relative;
    max-width: 90%;
    max-height: 90%;
    border: 1px solid var(--line);
    border-radius: var(--r-sm);
    overflow: hidden;
    background: var(--surface-2);
  }
  .board-wrap img { display: block; max-width: 100%; max-height: 70vh; object-fit: contain; }
  .scanline {
    position: absolute; left: 0; right: 0; top: 0; height: 6px;
    background: linear-gradient(180deg, transparent, rgba(62,166,255,0.65), transparent);
    box-shadow: 0 0 16px 4px rgba(62,166,255,0.45);
    animation: scanline 1.2s ease-in-out forwards;
  }
  .bbox {
    position: absolute;
    border: 1.5px solid var(--c);
    background: color-mix(in srgb, var(--c) 12%, transparent);
    pointer-events: none;
  }
  .bbox-label {
    position: absolute;
    top: -22px;
    left: 0;
    font-size: var(--fs-xs);
    padding: 1px 5px;
    background: rgba(14,17,22,0.85);
    color: var(--c);
    border: 1px solid var(--c);
    border-radius: 2px;
    white-space: nowrap;
  }

  .phases {
    display: flex;
    gap: 6px;
    padding: 8px 14px;
    border-top: 1px solid var(--line);
    background: var(--surface);
  }
  .phases .chip {
    flex: 1;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 10px;
    font-size: var(--fs-xs);
    border: 1px solid var(--line);
    border-radius: var(--r-sm);
    background: var(--surface-2);
    opacity: 0.45;
    transition: opacity 200ms ease, border-color 200ms ease, color 200ms ease;
  }
  .phases .chip.done {
    opacity: 1;
    border-color: var(--accent-data);
    color: var(--accent-data);
  }
  .phases .label { letter-spacing: 0.14em; }

  .verdict {
    padding: 10px 14px;
    text-align: center;
    letter-spacing: 0.18em;
    font-size: var(--fs-md);
    border-top: 1px solid var(--line);
  }
  .verdict[data-verdict='PASS'] {
    color: var(--accent-safe);
    background: color-mix(in srgb, var(--accent-safe) 12%, transparent);
  }
  .verdict[data-verdict='FAIL'] {
    color: var(--accent-fail);
    background: color-mix(in srgb, var(--accent-fail) 12%, transparent);
  }

  .completed-rail {
    border-top: 1px solid var(--line);
    background: var(--surface);
    padding: 8px 14px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .rail-label { font-size: var(--fs-xs); letter-spacing: 0.18em; flex-shrink: 0; }
  .completed-rail .rail {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    flex: 1;
    min-width: 0;
  }
</style>
