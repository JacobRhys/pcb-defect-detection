import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    // During `npm run dev`, forward /api/* to scripts/dev_endpoint.py, which
    // runs the real service/handler.py pipeline locally on port 8000.
    // The Cloudflare Pages Function is exercised by CI and by deploy, not by
    // local dev — see web/README.md for the two-terminal workflow.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
});
