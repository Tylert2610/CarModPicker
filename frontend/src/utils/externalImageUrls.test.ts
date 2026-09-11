/**
 * Tests for external image URL building.
 */

import { describe, expect, it } from 'vitest';
import { buildExternalImageUrl } from './externalImageUrls';

const WIX =
  'https://static.wixstatic.com/media/491c65_c908d21832d94d2383e540842ea8d659~mv2.webp';

describe('buildExternalImageUrl', () => {
  it('builds Wix thumbnail fill URL', () => {
    const u = buildExternalImageUrl(WIX, 'thumbnail');
    expect(u).toContain('/v1/fill/w_256,h_256/file.webp');
    expect(u).toMatch(/^https:\/\/static\.wixstatic\.com\/media\//);
  });

  it('builds Wix hero fit URL', () => {
    const u = buildExternalImageUrl(WIX, 'hero');
    expect(u).toContain('/v1/fit/w_1680,h_1680/file.webp');
  });

  it('does not double-transform Wix URLs', () => {
    const once = buildExternalImageUrl(WIX, 'hero')!;
    expect(buildExternalImageUrl(once, 'hero')).toBe(once);
  });

  it('returns unknown hosts unchanged', () => {
    const s3 =
      'https://example-bucket.s3.amazonaws.com/parts/1/img.webp?X-Amz-Signature=abc';
    expect(buildExternalImageUrl(s3, 'thumbnail')).toBe(s3);
  });

  it('adds width to Shopify CDN URLs', () => {
    const shop = 'https://cdn.shopify.com/s/files/1/2/3/products/photo.jpg?v=1';
    const u = buildExternalImageUrl(shop, 'thumbnail');
    expect(u).toContain('width=256');
  });
});
