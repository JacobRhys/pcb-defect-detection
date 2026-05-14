<script lang="ts">
  interface Props {
    values: number[];
    width?: number;
    height?: number;
    color?: string;
  }
  let { values, width = 200, height = 40, color = 'var(--accent-data)' }: Props = $props();

  let path = $derived.by(() => {
    if (values.length < 2) return '';
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(1, max - min);
    const stepX = width / (values.length - 1);
    return values
      .map((v, i) => {
        const x = i * stepX;
        const y = height - ((v - min) / span) * height;
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  });

  let last = $derived(values.length ? values[values.length - 1] : 0);
</script>

<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" class="spark" aria-hidden="true">
  {#if path}
    <path d={path} fill="none" stroke={color} stroke-width="1.5" />
  {/if}
</svg>

<style>
  .spark {
    width: 100%;
    height: 40px;
    display: block;
  }
</style>
