import { describe, expect, it } from 'vitest';
import { allowedExtensionIds, validateRedirectUri } from './ExtensionHandoff';

const ALLOWED = ['abcdefghijklmnopabcdefghijklmnop'];

describe('allowedExtensionIds', () => {
  it('reads a comma separated list', () => {
    expect(
      allowedExtensionIds({ VITE_ALLOWED_EXTENSION_IDS: 'aaa, bbb ,ccc' })
    ).toEqual(['aaa', 'bbb', 'ccc']);
  });

  it('trusts nothing when the variable is unset', () => {
    expect(allowedExtensionIds({})).toEqual([]);
    expect(allowedExtensionIds({ VITE_ALLOWED_EXTENSION_IDS: '' })).toEqual([]);
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
    expect(
      validateRedirectUri(
        `chrome-extension://evilevilevilevilevilevilevilevil/${ALLOWED[0]}`,
        ALLOWED
      )
    ).toBeNull();
  });
});
