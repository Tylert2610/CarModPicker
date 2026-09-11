/**
 * Tests for QR code encoding.
 */

import { describe, expect, it } from 'vitest';
import { encodeQrCode, qrCodeSvgPath } from './qrCode';

/** The provisioning URI shape the TOTP panel actually renders. */
const PROVISIONING_URI =
  'otpauth://totp/CarModPicker:someone@example.test?secret=JBSWY3DPEHPK3PXP&issuer=CarModPicker';

/** True when a 7x7 finder pattern sits with its top left corner at row/col. */
const hasFinderAt = (
  modules: boolean[][],
  row: number,
  col: number
): boolean => {
  for (let r = 0; r < 7; r += 1) {
    for (let c = 0; c < 7; c += 1) {
      const onBorder = r === 0 || r === 6 || c === 0 || c === 6;
      const inCore = r >= 2 && r <= 4 && c >= 2 && c <= 4;
      const expected = onBorder || inCore;
      if ((modules[row + r] as boolean[])[col + c] !== expected) return false;
    }
  }
  return true;
};

describe('encodeQrCode', () => {
  it('produces a square matrix at a valid version size', () => {
    const { size, modules } = encodeQrCode(PROVISIONING_URI);
    expect(size).toBeGreaterThanOrEqual(21);
    expect(size).toBeLessThanOrEqual(57);
    expect((size - 17) % 4).toBe(0);
    expect(modules).toHaveLength(size);
    for (const row of modules) expect(row).toHaveLength(size);
  });

  it('places the three finder patterns the standard requires', () => {
    const { size, modules } = encodeQrCode(PROVISIONING_URI);
    expect(hasFinderAt(modules, 0, 0)).toBe(true);
    expect(hasFinderAt(modules, 0, size - 7)).toBe(true);
    expect(hasFinderAt(modules, size - 7, 0)).toBe(true);
  });

  it('leaves the fourth corner free of a finder pattern', () => {
    const { size, modules } = encodeQrCode(PROVISIONING_URI);
    expect(hasFinderAt(modules, size - 7, size - 7)).toBe(false);
  });

  it('grows the symbol as the text gets longer', () => {
    const small = encodeQrCode('a');
    const large = encodeQrCode('a'.repeat(200));
    expect(large.size).toBeGreaterThan(small.size);
  });

  it('encodes the shortest input at the smallest version', () => {
    expect(encodeQrCode('a').size).toBe(21);
  });

  it('is deterministic, since mask selection is scored not random', () => {
    expect(encodeQrCode(PROVISIONING_URI).modules).toEqual(
      encodeQrCode(PROVISIONING_URI).modules
    );
  });

  it('produces a mixture of light and dark modules', () => {
    const { modules } = encodeQrCode(PROVISIONING_URI);
    const flat = modules.flat();
    expect(flat.some((m) => m)).toBe(true);
    expect(flat.some((m) => !m)).toBe(true);
  });

  it('refuses text longer than a version 10 symbol holds', () => {
    expect(() => encodeQrCode('a'.repeat(10000))).toThrow();
  });
});

describe('qrCodeSvgPath', () => {
  it('adds the four module quiet zone on every side', () => {
    const { size } = qrCodeSvgPath(PROVISIONING_URI);
    const matrix = encodeQrCode(PROVISIONING_URI);
    expect(size).toBe(matrix.size + 8);
  });

  it('reports a viewBox matching the padded size', () => {
    const { viewBox, size } = qrCodeSvgPath(PROVISIONING_URI);
    expect(viewBox).toBe(`0 0 ${String(size)} ${String(size)}`);
  });

  it('emits one path box per dark module', () => {
    const { path } = qrCodeSvgPath(PROVISIONING_URI);
    const { modules } = encodeQrCode(PROVISIONING_URI);
    const dark = modules.flat().filter(Boolean).length;
    expect(path.split('M').length - 1).toBe(dark);
  });

  it('keeps every box inside the padded viewBox', () => {
    const { path, size } = qrCodeSvgPath(PROVISIONING_URI);
    for (const [, x, y] of path.matchAll(/M(\d+) (\d+)h/g)) {
      expect(Number(x)).toBeGreaterThanOrEqual(4);
      expect(Number(y)).toBeGreaterThanOrEqual(4);
      expect(Number(x)).toBeLessThan(size - 4);
      expect(Number(y)).toBeLessThan(size - 4);
    }
  });
});
