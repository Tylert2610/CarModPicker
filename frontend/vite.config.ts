import { sentryVitePlugin } from '@sentry/vite-plugin';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react-swc';
import { defineConfig } from 'vite';

const isCIBuild = !!process.env.CI && !!process.env.SENTRY_AUTH_TOKEN;

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
      },
    },
  },
  preview: {
    allowedHosts: ['www.carmodpicker.com', 'carmodpicker.com'],
  },
  build: {
    sourcemap: 'hidden',
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules')) {
            return 'vendor';
          }
          return undefined;
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
});
