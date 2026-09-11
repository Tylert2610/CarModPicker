// Coverage for the real `client.ts`, the adapter between this application's
// call sites and `@webbpulse/api-client`.
//
// CRITICAL: setup.ts globally mocks `../api/client` so every other test file
// gets a stubbed apiClient. This file must exercise the REAL module, so each
// test calls `vi.doUnmock('./client')` + `vi.resetModules()` and then imports
// dynamically.
//
// These tests used to reach into axios internals (`defaults.paramsSerializer`,
// `interceptors.request.handlers[0].fulfilled`) to drive behaviour directly.
// The shared client has no such surface, and it does not need one: every
// behaviour below is observable on the `fetch` call the client makes, which is
// a stronger assertion than calling an interceptor by hand ever was. The
// env-driven base URL cases moved to `src/config/app.test.ts` along with the
// resolution logic itself.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/** The Request the client handed to fetch, for asserting on. */
interface Captured {
  url: string;
  init: RequestInit;
}

/**
 * Installs a fetch stub and returns the calls it captured.
 *
 * Resolves 200 with an empty JSON body by default, which is enough for every
 * request-shaping assertion here; cases that care about the response pass their
 * own.
 */
function stubFetch(response?: Response): Captured[] {
  const calls: Captured[] = [];
  vi.stubGlobal(
    'fetch',
    // The client always calls fetch with a string URL. Typing the parameter as
    // one rather than the full `RequestInfo | URL` keeps the capture honest: a
    // `Request` object has no meaningful string form, so `String()` on the
    // wider type would quietly produce "[object Object]".
    vi.fn((input: string, init?: RequestInit) => {
      calls.push({ url: input, init: init ?? {} });
      return Promise.resolve(
        response ??
          new Response(JSON.stringify({}), {
            status: 200,
            headers: { 'content-type': 'application/json' },
          })
      );
    })
  );
  return calls;
}

/** The single captured call, failing loudly rather than returning undefined. */
function only(calls: Captured[]): Captured {
  expect(calls).toHaveLength(1);
  const call = calls[0];
  if (call === undefined) throw new Error('no fetch call captured');
  return call;
}

const headerValue = (init: RequestInit, name: string): string | null =>
  new Headers(init.headers).get(name);

beforeEach(() => {
  vi.doUnmock('./client');
  vi.resetModules();
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe('client.ts — token helpers', () => {
  // Row 13 of docs/identity-adoption.md finished removing the bearer flow, and
  // the `localStorage` token store went with it. These three exports are kept
  // callable so the call sites that used to need them did not each grow a
  // branch, and what is asserted here is that they are inert: a later change
  // that quietly reintroduces a store has to delete a test that says why there
  // is not one.
  it('setStoredToken writes nothing anywhere a script can read back', async () => {
    const { setStoredToken } = await import('./client');
    setStoredToken('abc-123');
    // The old key, asserted literally. Section 7.1 of the identity standard
    // puts the access token in memory only, so a token reappearing here would
    // be the regression.
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.length).toBe(0);
  });

  it('getStoredToken returns null when no client has a token', async () => {
    // `getStoredToken` now reads `AuthClient`'s in-memory token rather than
    // storage. Nothing has signed in in this graph, so there is none.
    const { getStoredToken } = await import('./client');
    expect(getStoredToken()).toBeNull();
  });

  it('removeStoredToken is callable and clears nothing of its own', async () => {
    // The session is the httpOnly refresh cookie, and only the server can
    // revoke it, so the real end of a session is `AuthClient.logout()`. This
    // stays callable purely so `AuthContext`'s two error paths do not branch.
    const { getStoredToken, removeStoredToken } = await import('./client');
    expect(() => removeStoredToken()).not.toThrow();
    expect(getStoredToken()).toBeNull();
  });
});

describe('client.ts — credentials', () => {
  // Staging sits behind the access gate. Its CloudFront signed cookies are set
  // on the staging apex, so a call from www.staging to api.staging only carries
  // them when the client asks for credentials. Without this the gated staging
  // API answers 401.
  it('sends credentials so cross-subdomain cookies reach the API host', async () => {
    const calls = stubFetch();
    const { apiClient } = await import('./client');
    await apiClient.get('/health');
    expect(only(calls).init.credentials).toBe('include');
  });
});

describe('client.ts — query parameters', () => {
  it('expands array values as repeated keys (ids=1&ids=2&ids=3)', async () => {
    // The backend reads `ids` and `category_ids` as repeated keys. Bracket or
    // comma serialization would arrive as one unparseable value.
    const calls = stubFetch();
    const { apiClient } = await import('./client');
    await apiClient.get('/parts', { params: { ids: [1, 2, 3] } });
    expect(only(calls).url).toContain('ids=1&ids=2&ids=3');
  });

  it('passes URLSearchParams through, repeating keys it already holds', async () => {
    const calls = stubFetch();
    const { apiClient } = await import('./client');
    const params = new URLSearchParams();
    params.append('ids', '7');
    params.append('ids', '8');
    params.append('q', 'brake');
    await apiClient.get('/parts', { params });

    const { url } = only(calls);
    expect(url).toContain('ids=7&ids=8');
    expect(url).toContain('q=brake');
  });

  it('skips undefined and null values but keeps falsy 0 and empty string', async () => {
    const calls = stubFetch();
    const { apiClient } = await import('./client');
    await apiClient.get('/parts', {
      params: {
        skip: 0,
        name: '',
        missing: undefined,
        absent: null,
      },
    });

    const { url } = only(calls);
    expect(url).toContain('skip=0');
    expect(url).toContain('name=');
    expect(url).not.toContain('missing');
    expect(url).not.toContain('absent');
  });

  it('URL-encodes special characters in scalar values', async () => {
    const calls = stubFetch();
    const { apiClient } = await import('./client');
    // Percent encoding throughout, including the space: the shared client uses
    // encodeURIComponent rather than form encoding, so a space is %20 and not +.
    await apiClient.get('/search', { params: { q: 'a b&c=d' } });
    expect(only(calls).url).toContain('q=a%20b%26c%3Dd');
  });
});

describe('client.ts — authorization header', () => {
  // There is no longer a way to put a token in from the outside: the header is
  // filled by the `auth` provider the shared client is built with, which reads
  // `AuthClient`'s in-memory token. Driving the positive case would mean
  // standing up a signed in `AuthClient`, which `identityAuth.test.ts` already
  // covers at the seam that matters. What is left worth asserting here is that
  // an anonymous request carries no header at all.
  it('does not attach an Authorization header when there is no session', async () => {
    const calls = stubFetch();
    const { apiClient } = await import('./client');
    await apiClient.get('/users/me');
    expect(headerValue(only(calls).init, 'authorization')).toBeNull();
  });
});

describe('client.ts — token rotation', () => {
  // The bearer flow rotated tokens through an `x-new-access-token` response
  // header, which the client wrote back to `localStorage`. Both halves are gone:
  // the identity flow rotates through the refresh cookie inside `AuthClient`
  // instead. What is asserted is that the header is now inert, because a client
  // that still acted on it would be writing a token into a store that section
  // 7.1 of the identity standard says must not exist.
  it('ignores an x-new-access-token header rather than storing it', async () => {
    stubFetch(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: {
          'content-type': 'application/json',
          'x-new-access-token': 'rotated-token',
        },
      })
    );
    const { apiClient, getStoredToken } = await import('./client');
    await apiClient.get('/users/me');
    expect(getStoredToken()).toBeNull();
    expect(localStorage.getItem('access_token')).toBeNull();
  });
});

describe('client.ts — error contract', () => {
  it('rejects with an ApiError carrying the status and the envelope body', async () => {
    const envelope = {
      success: false,
      status: 404,
      message: 'Part not found',
      request_id: 'req-9',
      error_code: 'NOT_FOUND',
    };
    stubFetch(
      new Response(JSON.stringify(envelope), {
        status: 404,
        headers: { 'content-type': 'application/json' },
      })
    );
    const { apiClient, isApiErrorWithStatus } = await import('./client');

    const error: unknown = await apiClient
      .get('/parts/missing')
      .catch((caught: unknown) => caught);

    expect(isApiErrorWithStatus(error)).toBe(true);
    if (!isApiErrorWithStatus(error)) throw new Error('expected an ApiError');
    expect(error.status).toBe(404);
    expect(error.body).toEqual(envelope);
  });

  // A 401 is reported to the caller, not acted on here. Redirecting from the
  // transport would fight the router; AuthContext owns that decision.
  it('does not redirect on a 401', async () => {
    const { location } = window;
    stubFetch(new Response('{}', { status: 401 }));
    const { apiClient } = await import('./client');
    await expect(apiClient.get('/users/me')).rejects.toThrow();
    expect(window.location).toBe(location);
  });
});

describe('client.ts — request bodies', () => {
  it('sends a plain object as JSON', async () => {
    const calls = stubFetch();
    const { apiClient } = await import('./client');
    await apiClient.post('/parts', { name: 'Coilovers' });

    const { init } = only(calls);
    expect(headerValue(init, 'content-type')).toContain('application/json');
    expect(init.body).toBe(JSON.stringify({ name: 'Coilovers' }));
  });

  it('encodes a plain object as form-urlencoded when the caller asks for it', async () => {
    // Axios inferred the encoding from this header; the shared client infers it
    // from the body type, so the adapter converts the body rather than
    // forwarding the header. The path is arbitrary: what is under test is the
    // encoding, and the OAuth2 password form this was written against is one of
    // the routes row 13 of docs/identity-adoption.md deleted.
    const calls = stubFetch();
    const { apiClient } = await import('./client');
    await apiClient.post(
      '/some-form-endpoint',
      { username: 'alice', password: 'p@ss word' },
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    );

    const { init } = only(calls);
    // No explicit header: a URLSearchParams body makes fetch set
    // `application/x-www-form-urlencoded;charset=UTF-8` itself, the same way it
    // supplies a boundary for FormData.
    expect(init.body).toBeInstanceOf(URLSearchParams);
    expect(headerValue(init, 'content-type')).toBeNull();
    expect((init.body as URLSearchParams).toString()).toBe(
      'username=alice&password=p%40ss+word'
    );
  });

  it('passes FormData through without a Content-Type so the browser sets the boundary', async () => {
    // Image upload. A multipart request needs a boundary parameter in its
    // Content-Type, and only the runtime that serializes the body knows it.
    // Forwarding a bare `multipart/form-data` header would produce a request
    // the backend cannot parse, so the adapter drops it.
    const calls = stubFetch();
    const { apiClient } = await import('./client');
    const form = new FormData();
    form.append('file', new Blob(['bytes'], { type: 'image/png' }), 'car.png');

    await apiClient.post('/images', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    const { init } = only(calls);
    expect(init.body).toBeInstanceOf(FormData);
    expect(headerValue(init, 'content-type')).toBeNull();
  });

  it('forwards headers that are not content encoding directives', async () => {
    const calls = stubFetch();
    const { apiClient } = await import('./client');
    await apiClient.post(
      '/parts',
      { name: 'x' },
      { headers: { 'X-Trace': 'abc' } }
    );
    expect(headerValue(only(calls).init, 'x-trace')).toBe('abc');
  });
});

describe('client.ts — response shape', () => {
  it('resolves with the parsed body under data', async () => {
    stubFetch(
      new Response(JSON.stringify({ id: 5, name: 'Coilovers' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    );
    const { apiClient } = await import('./client');
    const response = await apiClient.get<{ id: number; name: string }>(
      '/parts/5'
    );
    expect(response.data).toEqual({ id: 5, name: 'Coilovers' });
  });
});
