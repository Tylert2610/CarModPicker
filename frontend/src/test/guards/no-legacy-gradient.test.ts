/**
 * Guard: no Tailwind v3 gradient class names remain in source.
 */

import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

const LEGACY_GRADIENT_PREFIX = ['bg', 'gradient', 'to'].join('-') + '-';
const LEGACY_GRADIENT_RE = new RegExp(LEGACY_GRADIENT_PREFIX);

describe('FE-05: no Tailwind v3 legacy gradient class names in source', () => {
  it('no source file contains the legacy gradient prefix', () => {
    const srcDir = resolve(__dirname, '..', '..');
    const files = globSync('src/**/*.{ts,tsx}', {
      cwd: srcDir,
      absolute: true,
    });
    const allowlist = new Set([
      resolve(__dirname, 'no-legacy-gradient.test.ts'),
    ]);
    const violations: Array<{ file: string; line: number; match: string }> = [];
    for (const file of files) {
      if (allowlist.has(file)) continue;
      const lines = readFileSync(file, 'utf8').split('\n');
      lines.forEach((line, i) => {
        if (LEGACY_GRADIENT_RE.test(line)) {
          violations.push({ file, line: i + 1, match: line.trim() });
        }
      });
    }
    expect(violations).toEqual([]);
  });
});
