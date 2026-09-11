/**
 * Token storage, local to this application.
 *
 * This used to be `TokenStore` from `@webbpulse/auth`. Version 0.4.0 of that
 * package removed the whole `localStorage`-backed token store rather than
 * deprecating it: section 7.1 of the identity standard holds the access token
 * in memory only, refreshed from an httpOnly cookie, and leaving the storage
 * class exported invites exactly the use the design exists to stop.
 *
 * CarModPicker has not adopted the shared identity service, so it still holds a
 * bearer token in `localStorage` and there is nothing in 0.5.0 to hold it
 * instead. `AuthClient` is not a drop-in replacement, it is a different
 * mechanism, and moving to it is the identity migration rather than a
 * dependency bump. So the code comes back here unchanged, which keeps this bump
 * behaviour-neutral and leaves the migration a separate, deliberate change.
 *
 * The behaviour below is byte-for-byte the 0.3.0 implementation, minus the
 * two-application key comment that no longer applies to a single consumer.
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
 * Returns `localStorage` when it is usable, an in memory store otherwise.
 *
 * The probe is a real write. Safari in private mode, and any browser set to
 * block site data, exposes a `localStorage` object whose `setItem` throws, so
 * a presence check alone is not enough.
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
