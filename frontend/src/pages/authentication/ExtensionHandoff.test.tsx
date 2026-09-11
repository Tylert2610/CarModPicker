// The extension handoff's redirect target validation.
//
// This is the security-critical half of the page: `redirect_uri` arrives in a
// query parameter, which means it arrives from whoever built the link, and
// what is about to be appended to it is a credential. Every case below is a
// URL that must not be redirected to.
import { describe, expect, it } from 'vitest';
import { allowedExtensionIds, validateRedirectUri } from './ExtensionHandoff';

const ALLOWED = ['abcdefghijklmnopabcdefghijklmnop'];

describe('allowedExtensionIds', () => {
  it('reads a comma separated list', () => {
    expect(
      allowedExtensionIds({ VITE_EXTENSION_IDS: 'aaa, bbb ,ccc' })
    ).toEqual(['aaa', 'bbb', 'ccc']);
  });

  it('trusts nothing when the variable is unset', () => {
    // The safe default for an environment that forgot to set it. An empty
    // allowlist refuses every extension rather than permitting any.
    expect(allowedExtensionIds({})).toEqual([]);
    expect(allowedExtensionIds({ VITE_EXTENSION_IDS: '' })).toEqual([]);
  });
});

describe('validateRedirectUri', () => {
  it('accepts an allowlisted extension origin', () => {
    expect(
      validateRedirectUri(`chrome-extension://${ALLOWED[0]}/callback`, ALLOWED)
    ).toBe(`chrome-extension://${ALLOWED[0]}/callback`);
  });

  it('refuses an extension that is not on the list', () => {
    expect(
      validateRedirectUri(
        'chrome-extension://zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz/callback',
        ALLOWED
      )
    ).toBeNull();
  });

  it('refuses every scheme but chrome-extension', () => {
    // The whole point: an https target is a redirect off this origin entirely,
    // carrying a credential in its fragment.
    for (const uri of [
      `https://${ALLOWED[0]}/callback`,
      `http://${ALLOWED[0]}/callback`,
      `javascript:alert(1)//${ALLOWED[0]}`,
      `data:text/html,<script>`,
      `//${ALLOWED[0]}/callback`,
    ]) {
      expect(validateRedirectUri(uri, ALLOWED)).toBeNull();
    }
  });

  it('refuses a missing or unparseable target', () => {
    expect(validateRedirectUri(null, ALLOWED)).toBeNull();
    expect(validateRedirectUri('', ALLOWED)).toBeNull();
    expect(validateRedirectUri('not a url', ALLOWED)).toBeNull();
  });

  it('refuses everything when the allowlist is empty', () => {
    expect(
      validateRedirectUri(`chrome-extension://${ALLOWED[0]}/callback`, [])
    ).toBeNull();
  });

  it('matches on the host, not on a prefix of the whole URL', () => {
    // A target whose *path* happens to contain an allowlisted id is a
    // different extension, and a naive `startsWith` would have taken it.
    expect(
      validateRedirectUri(
        `chrome-extension://evilevilevilevilevilevilevilevil/${ALLOWED[0]}`,
        ALLOWED
      )
    ).toBeNull();
  });
});
