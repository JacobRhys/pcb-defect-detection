import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    // Static export: SvelteKit emits a fully prerendered site into /web/build.
    // Cloudflare Pages serves that directly; /web/functions handles /api/*.
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: undefined,
      precompress: false,
      strict: true
    }),
    // Match the prompt's directory layout: public/ holds static assets
    // (samples + favicon) instead of the SvelteKit default `static/`.
    files: {
      assets: 'public'
    },
    alias: {
      $components: 'src/lib/components'
    }
  }
};

export default config;
