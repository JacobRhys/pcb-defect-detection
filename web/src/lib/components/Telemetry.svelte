<script lang="ts">
  import KPI from './KPI.svelte';
  import Sparkline from './Sparkline.svelte';
  import DefectMix from './DefectMix.svelte';
  import NodeIndicator from './NodeIndicator.svelte';
  import LogPanel from './LogPanel.svelte';

  import {
    avgLatency,
    defectCounts,
    latencyHistory,
    logRows,
    node,
    sessionTotals,
    throughput,
    totalDefects,
    yieldPct
  } from '$lib/state';
</script>

<aside class="telemetry" aria-label="Line telemetry">
  <header>
    <span class="title mono">TELEMETRY</span>
  </header>

  <NodeIndicator state={$node} />

  <div class="kpi-grid">
    <KPI label="THROUGHPUT" unit="boards/min" window="rolling 60 s" value={$throughput} accent="var(--accent-data)" />
    <KPI label="YIELD"      unit="%"          window="session"      value={$yieldPct} decimals={1} accent="var(--accent-safe)" />
    <KPI label="LATENCY"    unit="ms"         window="rolling 20"   value={$avgLatency} accent="var(--accent-warn)" />
    <KPI label="DEFECTS"    unit="count"      window="session"      value={$totalDefects} accent="var(--accent-fail)" />
  </div>

  <section class="panel">
    <header class="panel-head">
      <span class="mono muted">DEFECT MIX</span>
      <span class="mono muted">{$sessionTotals.pass + $sessionTotals.fail} boards</span>
    </header>
    <DefectMix counts={$defectCounts} />
  </section>

  <section class="panel">
    <header class="panel-head">
      <span class="mono muted">LATENCY · LAST 50</span>
      <span class="mono muted">{$latencyHistory.length}</span>
    </header>
    <Sparkline values={$latencyHistory} />
  </section>

  <section class="panel">
    <header class="panel-head">
      <span class="mono muted">LOG</span>
    </header>
    <LogPanel rows={$logRows} rowCount={8} />
  </section>
</aside>

<style>
  .telemetry {
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 100%;
    background: var(--surface);
    border-left: 1px solid var(--line);
    padding: 12px;
    overflow-y: auto;
    min-width: 0;
  }
  header { display: flex; justify-content: space-between; align-items: center; }
  .title {
    font-size: var(--fs-sm);
    letter-spacing: 0.16em;
    color: var(--accent-data);
  }
  .kpi-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .panel { display: flex; flex-direction: column; gap: 6px; }
  .panel-head { display: flex; justify-content: space-between; font-size: var(--fs-xs); letter-spacing: 0.12em; }
</style>
