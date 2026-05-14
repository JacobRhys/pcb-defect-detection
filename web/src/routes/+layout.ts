// Pure static export: every page is prerendered at build, no client-side
// router-served HTML for unknown paths, no SSR.
export const prerender = true;
export const ssr = false;
export const trailingSlash = 'never';
