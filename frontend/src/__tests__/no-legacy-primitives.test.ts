/**
 * Guard: nothing imports the retired common and buttons primitives.
 */

import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

/**
 * Fails the suite when retired primitives reappear: imports from the removed
 * `common/` and `buttons/` directories, raw palette utilities outside the token
 * stylesheets, legacy glass classes, and hand-rolled shapes that `ui/` replaces.
 */
const LEGACY_PRIMITIVE_RE = /from\s+['"](?:\.\.\/)+(?:common|buttons)\//;

const RAW_PALETTE_RE =
  /(?:text|bg|border|ring|from|to|via)-(?:primary|neutral|emerald|indigo|amber|rose)-[0-9]/;
const TEXT_ACCENT_RE = /text-accent-(?:emerald|amber|rose|purple)/;

const GLASS_CLASS_RE = new RegExp('\\bgla' + 'ss-(?:card|button)?\\b');
const GLASS_CLASSNAME_RE = new RegExp('className=.*\\bgla' + 'ss\\b');

const HAND_ROLLED_TEXTAREA_RE = /<textarea\s/;
const INLINE_LOADING_OVERLAY_RE =
  /className="absolute inset-0 bg-background\/80 backdrop-blur-sm/;
const INLINE_BADGE_FACTORY_RE =
  /(?:const|function)\s+(?:get(?:Status|Priority)Badge)/;

const SRC_DIR = resolve(__dirname, '..');
const GUARD_FILE = resolve(__dirname, 'no-legacy-primitives.test.ts');

const COMMON_IGNORES = ['**/node_modules/**', '**/dist/**', '**/coverage/**'];

interface Violation {
  file: string;
  line: number;
  match: string;
}

function scan(
  globs: string[],
  patterns: RegExp[],
  allowlist: Set<string>,
  ignore: string[] = COMMON_IGNORES
): Violation[] {
  const seen = new Set<string>();
  const violations: Violation[] = [];
  for (const pattern of globs) {
    const files = globSync(pattern, {
      cwd: SRC_DIR,
      absolute: true,
      ignore,
    });
    for (const file of files) {
      if (seen.has(file)) continue;
      seen.add(file);
      if (allowlist.has(file)) continue;
      const lines = readFileSync(file, 'utf8').split('\n');
      lines.forEach((line, i) => {
        for (const re of patterns) {
          if (re.test(line)) {
            violations.push({ file, line: i + 1, match: line.trim() });
            break;
          }
        }
      });
    }
  }
  return violations;
}

describe('R017 / M002-S12: no legacy components/common or components/buttons imports', () => {
  it('no source file imports from components/common/ or components/buttons/', () => {
    const files = globSync('**/*.{ts,tsx}', {
      cwd: SRC_DIR,
      absolute: true,
      ignore: [
        ...COMMON_IGNORES,
        '__tests__/**',
        'components/common/**',
        'components/buttons/**',
      ],
    });

    const allowlist = new Set<string>([GUARD_FILE]);

    const violations: Violation[] = [];
    for (const file of files) {
      if (allowlist.has(file)) continue;
      const lines = readFileSync(file, 'utf8').split('\n');
      lines.forEach((line, i) => {
        if (LEGACY_PRIMITIVE_RE.test(line)) {
          violations.push({
            file,
            line: i + 1,
            match: line.trim(),
          });
        }
      });
    }

    expect(violations).toEqual([]);
  });
});

describe('M003-S06: no legacy design-system re-entry', () => {
  it('no raw legacy palette utilities outside index.css/tokens.css', () => {
    const consumerGlobs = [
      'components/**/*.{ts,tsx,css}',
      'pages/**/*.{ts,tsx,css}',
      'contexts/**/*.{ts,tsx,css}',
      'hooks/**/*.{ts,tsx,css}',
      'api/**/*.{ts,tsx,css}',
      'lib/**/*.{ts,tsx,css}',
      '__tests__/**/*.{ts,tsx,css}',
    ];
    const allowlist = new Set<string>([
      GUARD_FILE,
      resolve(SRC_DIR, 'index.css'),
      resolve(SRC_DIR, 'styles/tokens.css'),
    ]);
    const violations = scan(
      consumerGlobs,
      [RAW_PALETTE_RE, TEXT_ACCENT_RE],
      allowlist
    );
    expect(violations).toEqual([]);
  });

  it('no glassNAME class references in consumer code', () => {
    const consumerGlobs = [
      'components/**/*.{ts,tsx,css}',
      'pages/**/*.{ts,tsx,css}',
      'contexts/**/*.{ts,tsx,css}',
      'hooks/**/*.{ts,tsx,css}',
      'api/**/*.{ts,tsx,css}',
      'lib/**/*.{ts,tsx,css}',
      '__tests__/**/*.{ts,tsx,css}',
    ];
    const allowlist = new Set<string>([
      GUARD_FILE,
      resolve(SRC_DIR, 'index.css'),
      resolve(SRC_DIR, 'styles/tokens.css'),
    ]);
    const violations = scan(
      consumerGlobs,
      [GLASS_CLASS_RE, GLASS_CLASSNAME_RE],
      allowlist
    );
    expect(violations).toEqual([]);
  });

  it('no hand-rolled patterns now that ui/* primitives exist', () => {
    const consumerGlobs = [
      'components/**/*.{ts,tsx}',
      'pages/**/*.{ts,tsx}',
      'contexts/**/*.{ts,tsx}',
      'hooks/**/*.{ts,tsx}',
      'api/**/*.{ts,tsx}',
      'lib/**/*.{ts,tsx}',
    ];
    const allowlist = new Set<string>([
      GUARD_FILE,
      resolve(SRC_DIR, 'components/ui/textarea.tsx'),
      resolve(SRC_DIR, 'components/ui/loading-overlay.tsx'),
      resolve(SRC_DIR, 'components/ui/status-badge.tsx'),
    ]);
    const patterns = [
      HAND_ROLLED_TEXTAREA_RE,
      INLINE_LOADING_OVERLAY_RE,
      INLINE_BADGE_FACTORY_RE,
    ];
    const violations = scan(consumerGlobs, patterns, allowlist);
    expect(violations).toEqual([]);
  });
});
