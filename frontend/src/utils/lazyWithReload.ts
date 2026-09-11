import { type ComponentType, lazy } from 'react';

const RELOAD_KEY = 'cmp_chunk_reload_attempted';

function isChunkLoadError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const message = error.message || '';
  return (
    error.name === 'ChunkLoadError' ||
    /Failed to fetch dynamically imported module/i.test(message) ||
    /Importing a module script failed/i.test(message) ||
    /error loading dynamically imported module/i.test(message)
  );
}

/**
 * Wraps `React.lazy` so a failed dynamic import, usually a stale index.html
 * naming chunks a deploy removed, forces one hard reload. A sessionStorage flag
 * stops a genuine failure from looping.
 */
export function lazyWithReload<
  T extends ComponentType<Record<string, unknown>>,
>(factory: () => Promise<{ default: T }>) {
  return lazy<T>(async () => {
    try {
      const mod = await factory();
      sessionStorage.removeItem(RELOAD_KEY);
      return mod;
    } catch (error) {
      if (isChunkLoadError(error) && !sessionStorage.getItem(RELOAD_KEY)) {
        sessionStorage.setItem(RELOAD_KEY, '1');
        window.location.reload();
        return new Promise<{ default: T }>(() => {});
      }
      throw error;
    }
  });
}
