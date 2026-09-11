import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { useCookieConsent } from './useCookieConsent';

const STORAGE_KEY = 'cookie_consent_v1';

describe('useCookieConsent', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it('returns null consent when localStorage is empty', () => {
    const { result } = renderHook(() => useCookieConsent());

    expect(result.current.consent).toBeNull();
    expect(typeof result.current.accept).toBe('function');
    expect(typeof result.current.reject).toBe('function');
    expect(typeof result.current.reset).toBe('function');
  });

  it('hydrates existing accepted value from localStorage on mount', () => {
    window.localStorage.setItem(STORAGE_KEY, 'accepted');

    const { result } = renderHook(() => useCookieConsent());

    expect(result.current.consent).toBe('accepted');
  });

  it('accept() persists "accepted" to localStorage and updates state', () => {
    const { result } = renderHook(() => useCookieConsent());

    act(() => {
      result.current.accept();
    });

    expect(result.current.consent).toBe('accepted');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('accepted');
  });

  it('reject() persists "rejected" to localStorage and updates state', () => {
    const { result } = renderHook(() => useCookieConsent());

    act(() => {
      result.current.reject();
    });

    expect(result.current.consent).toBe('rejected');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('rejected');
  });

  it('reset() clears localStorage and state back to null', () => {
    window.localStorage.setItem(STORAGE_KEY, 'accepted');
    const { result } = renderHook(() => useCookieConsent());

    expect(result.current.consent).toBe('accepted');

    act(() => {
      result.current.reset();
    });

    expect(result.current.consent).toBeNull();
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('syncs across instances via the cookie-consent-change CustomEvent', () => {
    const { result: a } = renderHook(() => useCookieConsent());
    const { result: b } = renderHook(() => useCookieConsent());

    act(() => {
      a.current.accept();
    });

    expect(a.current.consent).toBe('accepted');
    expect(b.current.consent).toBe('accepted');
  });
});
