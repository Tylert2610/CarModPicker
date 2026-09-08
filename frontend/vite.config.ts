import { sentryVitePlugin } from '@sentry/vite-plugin';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react-swc';
import { defineConfig } from 'vite';

// D-34 + Landmine 13: CI-only sourcemap upload. Local builds (no CI env +
// no auth token) silently skip the plugin — no upload, no noise.
const isCIBuild = !!process.env.CI && !!process.env.SENTRY_AUTH_TOKEN;

// https://vite.dev/config/
/** `{ key: value }` when the value is set, and nothing at all when it is not. */
const whenSet = <K extends string>(
  key: K,
  value: string | undefined
): Record<K, string> | Record<string, never> =>
  value === undefined ? {} : ({ [key]: value } as Record<K, string>);

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    ...(isCIBuild
      ? [
          sentryVitePlugin({
            // Every key is spread rather than assigned, so an unset variable
            // leaves the key absent and the plugin falls back to its own
            // default. Assigning an explicit `undefined` is not the same thing
            // to the plugin, and is what the shared tsconfig's
            // exactOptionalPropertyTypes flagged here.
            ...whenSet('org', process.env.SENTRY_ORG),
            ...whenSet('project', process.env.SENTRY_PROJECT),
            ...whenSet('authToken', process.env.SENTRY_AUTH_TOKEN),
            ...(process.env.SENTRY_RELEASE !== undefined
              ? { release: { name: process.env.SENTRY_RELEASE } }
              : {}),
          }),
        ]
      : []),
  ],
  server: {
    port: 4000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Optionally, rewrite the path if your backend expects no '/api' prefix:
        // rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  preview: {
    allowedHosts: ['www.carmodpicker.com', 'carmodpicker.com'],
  },
  build: {
    // Landmine 12: 'hidden' emits .map files so the vite-plugin has maps to
    // upload, BUT strips the `//# sourceMappingURL=...` comment from bundle
    // files so end users can't fetch them from the CDN.
    sourcemap: 'hidden',
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Single vendor chunk for all node_modules to avoid circular chunks
          // (e.g. vendor <-> vendor-react when other libs depend on React)
          if (id.includes('node_modules')) {
            return 'vendor';
          }
          // App code: no manual chunks; Rollup splits by lazy() routes in
          // App.tsx. Returned explicitly because `undefined` is what tells
          // Rollup to decide, and an implicit fall-through reads as an
          // oversight.
          return undefined;
        },
      },
    },
    chunkSizeWarningLimit: 600, // Increase limit slightly to reduce warnings
  },
});
