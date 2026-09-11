import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { useDocumentMeta } from './useDocumentMeta';

describe('useDocumentMeta', () => {
  let originalTitle = '';
  let originalHead = '';

  beforeEach(() => {
    originalTitle = document.title;
    originalHead = document.head.innerHTML;
  });

  afterEach(() => {
    document.title = originalTitle;
    document.head.innerHTML = originalHead;
  });

  it('sets document.title to "<title> | CarModPicker" by default', () => {
    renderHook(() => useDocumentMeta({ title: 'Home' }));
    expect(document.title).toBe('Home | CarModPicker');
  });

  it('does not duplicate site name when title already contains it', () => {
    renderHook(() => useDocumentMeta({ title: 'About CarModPicker' }));
    expect(document.title).toBe('About CarModPicker');
  });

  it('writes meta description + og tags on mount', () => {
    renderHook(() =>
      useDocumentMeta({ title: 'Parts', description: 'Browse all parts' })
    );

    const desc = document.head.querySelector<HTMLMetaElement>(
      'meta[name="description"]'
    );
    const ogTitle = document.head.querySelector<HTMLMetaElement>(
      'meta[property="og:title"]'
    );
    const ogDesc = document.head.querySelector<HTMLMetaElement>(
      'meta[property="og:description"]'
    );

    expect(desc?.getAttribute('content')).toBe('Browse all parts');
    expect(ogTitle?.getAttribute('content')).toBe('Parts | CarModPicker');
    expect(ogDesc?.getAttribute('content')).toBe('Browse all parts');
  });

  it('sets canonical link and og:url when canonicalPath is provided', () => {
    renderHook(() =>
      useDocumentMeta({ title: 'Parts', canonicalPath: '/parts' })
    );

    const canonical = document.head.querySelector<HTMLLinkElement>(
      'link[rel="canonical"]'
    );
    const ogUrl = document.head.querySelector<HTMLMetaElement>(
      'meta[property="og:url"]'
    );

    expect(canonical?.getAttribute('href')).toBe(
      'https://www.carmodpicker.com/parts'
    );
    expect(ogUrl?.getAttribute('content')).toBe(
      'https://www.carmodpicker.com/parts'
    );
  });

  it('does not create a canonical link when canonicalPath is omitted', () => {
    renderHook(() => useDocumentMeta({ title: 'Parts' }));
    const canonical = document.head.querySelector('link[rel="canonical"]');
    expect(canonical).toBeNull();
  });
});
