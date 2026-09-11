/**
 * Guard: browser source reads import.meta.env, never process.env.
 */

import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

describe('FE-02: no process.env in frontend browser source (use import.meta.env.VITE_*)', () => {
  it('no non-allowlisted src file contains process.env', () => {
    const srcDir = resolve(__dirname, '..', '..');
    const files = globSync('src/**/*.{ts,tsx}', {
      cwd: srcDir,
      absolute: true,
    });
    const allowlist = new Set([
      resolve(srcDir, 'src/lib/sentry.ts'),
      resolve(__dirname, 'no-process-env.test.ts'),
    ]);
    const violations: Array<{ file: string; line: number; match: string }> = [];
    for (const file of files) {
      if (allowlist.has(file)) continue;
      const lines = readFileSync(file, 'utf8').split('\n');
      lines.forEach((line, i) => {
        if (/\bprocess\.env\b/.test(line)) {
          violations.push({ file, line: i + 1, match: line.trim() });
        }
      });
    }
    expect(violations).toEqual([]);
  });
});
