/**
 * Bearer token storage, local to this application since `@webbpulse/auth` 0.4.0
 * removed its `localStorage` backed store. Falls back to memory where
 * `localStorage` is unusable.
 */

/** Minimal storage contract. `localStorage` satisfies it. */
export interface TokenStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

/**
 * In memory storage. The default when no Storage is available, which covers
 * server side rendering, tests, and a browser with site data blocked, where
 * touching `localStorage` throws rather than returning null.
 */
export class MemoryTokenStorage implements TokenStorage {
  private readonly values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }
}

/**
 * Returns `localStorage` when usable, an in memory store otherwise. Probes with
 * a real write, since a blocked store is present but throws on `setItem`.
 */
export function defaultTokenStorage(): TokenStorage {
  try {
    const probeKey = '__webbpulse_probe__';
    globalThis.localStorage.setItem(probeKey, '1');
    globalThis.localStorage.removeItem(probeKey);
    return globalThis.localStorage;
  } catch {
    return new MemoryTokenStorage();
  }
}

/** Reads and writes one token under one key. */
export class TokenStore {
  private readonly key: string;
  private readonly storage: TokenStorage;

  constructor(key: string, storage: TokenStorage = defaultTokenStorage()) {
    this.key = key;
    this.storage = storage;
  }

  get(): string | null {
    try {
      return this.storage.getItem(this.key);
    } catch {
      return null;
    }
  }

  set(token: string): void {
    try {
      this.storage.setItem(this.key, token);
    } catch (error) {
      void error;
    }
  }

  clear(): void {
    try {
      this.storage.removeItem(this.key);
    } catch (error) {
      void error;
    }
  }
}
