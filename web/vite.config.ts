import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    // During `npm run dev`, forward /api requests to the Cloudflare Pages
    // local dev server (wrangler pages dev) on port 8788. See web/README.md.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8788',
        changeOrigin: true
      }
    }
  }
});
