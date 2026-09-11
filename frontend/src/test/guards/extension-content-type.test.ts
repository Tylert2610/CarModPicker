/**
 * Guard: the Chrome extension must send a Content-Type FastAPI accepts.
 */

import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

/**
 * Returns the index just past the brace matching the one at `startIdx`, or -1
 * when unbalanced. Skips string literals and comments, which is enough for the
 * shape of a real fetch options object without being a full parser.
 */
function findMatchingBrace(src: string, startIdx: number): number {
  if (src[startIdx] !== '{') return -1;
  let depth = 0;
  let i = startIdx;
  const len = src.length;
  while (i < len) {
    const ch = src[i];
    if (ch === '/' && src[i + 1] === '/') {
      const nl = src.indexOf('\n', i + 2);
      if (nl === -1) return -1;
      i = nl + 1;
      continue;
    }
    if (ch === '/' && src[i + 1] === '*') {
      const end = src.indexOf('*/', i + 2);
      if (end === -1) return -1;
      i = end + 2;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      const quote = ch;
      i++;
      while (i < len) {
        const c = src[i];
        if (c === '\\') {
          i += 2;
          continue;
        }
        if (c === quote) {
          i++;
          break;
        }
        if (quote === '`' && c === '$' && src[i + 1] === '{') {
          const end = findMatchingBrace(src, i + 1);
          if (end === -1) return -1;
          i = end;
          continue;
        }
        i++;
      }
      continue;
    }
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return i + 1;
    }
    i++;
  }
  return -1;
}

/**
 * Extracts every options-object literal passed to `fetch(...)`, balancing braces
 * so a nested literal such as `headers` does not truncate the match.
 */
function extractFetchOptionsObjects(src: string): string[] {
  const results: string[] = [];
  const fetchRe = /\bfetch\s*\(/g;
  let m: RegExpExecArray | null;
  while ((m = fetchRe.exec(src)) !== null) {
    let i = m.index + m[0].length;
    let parenDepth = 1;
    while (i < src.length && parenDepth > 0) {
      const ch = src[i];
      if (ch === '"' || ch === "'" || ch === '`') {
        const quote = ch;
        i++;
        while (i < src.length) {
          const c = src[i];
          if (c === '\\') {
            i += 2;
            continue;
          }
          if (c === quote) {
            i++;
            break;
          }
          if (quote === '`' && c === '$' && src[i + 1] === '{') {
            const end = findMatchingBrace(src, i + 1);
            if (end === -1) break;
            i = end;
            continue;
          }
          i++;
        }
        continue;
      }
      if (ch === '(') parenDepth++;
      else if (ch === ')') {
        parenDepth--;
        if (parenDepth === 0) break;
      } else if (ch === '{' && parenDepth === 1) {
        const end = findMatchingBrace(src, i);
        if (end === -1) break;
        results.push(src.slice(i, end));
        i = end;
        continue;
      }
      i++;
    }
  }
  return results;
}

describe('QUAL-06: Chrome extension POST Content-Type compliance (FastAPI 0.132+ strict)', () => {
  it('every fetch POST sets application/json Content-Type or uses FormData', () => {
    const extDir = resolve(__dirname, '..', '..', '..', 'chrome-extension');
    const files = globSync('src/**/*.ts', { cwd: extDir, absolute: true });
    const methodPostRe = /\bmethod\s*:\s*["']POST["']/;
    const violations: string[] = [];
    for (const file of files) {
      const src = readFileSync(file, 'utf8');
      const optionsBlocks = extractFetchOptionsObjects(src);
      for (const block of optionsBlocks) {
        if (!methodPostRe.test(block)) continue;
        const hasJsonHeader =
          /["']Content-Type["']\s*:\s*["']application\/json["']/.test(block);
        const hasFormData = /body\s*:\s*(formData|\w*FormData)/i.test(block);
        if (!hasJsonHeader && !hasFormData) {
          violations.push(`${file}: ${block.slice(0, 200)}`);
        }
      }
    }
    expect(violations).toEqual([]);
  });
});
