import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react-swc';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    // Vitest's default include picks up e2e/*.spec.ts which Playwright owns.
    // Constrain to src/ so npm test only runs unit/integration suites.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', 'e2e/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      // Vitest 4 removed `coverage.all`; the report now covers only files a
      // test imported unless `include` names them. The thresholds below were
      // calibrated against the whole app source tree, so name it explicitly to
      // keep untested files counted rather than silently dropped.
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/coverage/**',
        'dist/',
        'build/',
        // D-13 (Phase 8): app bootstrap; executes once on mount, not
        // meaningfully testable as a unit.
        'src/main.tsx',
        // D-13 (Phase 8): pure TypeScript types; no executable runtime code.
        'src/types/Api.ts',
      ],
      // SAFE-03 threshold enforcement enabled by Phase 8 plan 08-20.
      // Phase 8 lifted frontend coverage from the 2026-04-22 baseline (lines 0.43%)
      // to meet D-06 targets. See .planning/phases/08-frontend-coverage-expansion/
      // for per-plan coverage deltas and 08-FAIL-FORCE-PROOF.txt for enforcement evidence.
      //
      // Rebased for vitest 5 (was lines 60, functions 50, branches 50,
      // statements 60). Vitest 4 made AST-aware remapping the default and only
      // remapping method, replacing v8-to-istanbul. It counts statements far
      // more precisely, so the denominator collapsed: measured over an
      // identical 178 file set, the same tests against the same code report
      // 17688/27387 (64.59%) under vitest 3 and 3953/7956 (49.69%) under
      // vitest 5, a 3.44x smaller statement universe. Per file, carUtils.ts
      // goes from 64 statements to 23 and AuthContext.tsx from 86 to 41.
      // No test and no application code changed.
      //
      // Each number keeps the headroom the old threshold had, except branches.
      // Its old value of 50 was clearing by 18.89 points, so carrying that
      // slack across would have produced a gate that guards almost nothing;
      // 38 sits just under the real 41.57 instead.
      thresholds: {
        lines: 51,
        functions: 41,
        branches: 38,
        statements: 49,
      },
    },
  },
});
