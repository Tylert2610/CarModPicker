// Lint configuration, layered on @webbpulse/eslint-config.
//
// The shared `reactConfig` supplies what used to be spelled out here: the
// ignores, `js.configs.recommended` plus `recommendedTypeChecked`, the browser
// globals, the five `no-unsafe-*` rules promoted to errors, the react-hooks and
// react-refresh rules, the Node override for config files, and
// `eslint-config-prettier` last. CarModPicker's level of strictness is what the
// shared base was set to, so nothing was relaxed to adopt it.
//
// What stays here is what is genuinely local: the react-x and react-dom rule
// sets (the shared config takes the plugins from the consumer rather than
// forcing them on Portfolio, which does not use them) and the M002/S12
// enforcement gate below.
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import reactX from 'eslint-plugin-react-x';
import reactDom from 'eslint-plugin-react-dom';
import { reactConfig } from '@webbpulse/eslint-config/react';

export default [
  // The Playwright specs sit outside every tsconfig project, so the typed rules
  // cannot parse them, and they were not linted before this migration either.
  // Ignored rather than narrowing `files`, because narrowing would also drop
  // the shared config's Node override for `vite.config.ts`.
  { ignores: ['e2e/'] },
  ...reactConfig({
    project: ['./tsconfig.app.json'],
    tsconfigRootDir: import.meta.dirname,
    plugins: {
      'react-refresh': reactRefresh,
      'react-hooks': reactHooks,
      'react-x': reactX,
      'react-dom': reactDom,
    },
    rules: {
      ...reactX.configs['recommended-typescript'].rules,
      ...reactDom.configs.recommended.rules,
      // Rules that assume a React version this application is not on.
      'react-x/no-use-context': 'off',
      'react-x/no-context-provider': 'off',
      'react-x/unsupported-syntax': 'off',
      // M002/S12 R017 enforcement gate (redundant safety alongside the
      // src/__tests__/no-legacy-primitives.test.ts vitest guard). Blocks
      // any future PR from re-importing the retired legacy primitives at
      // lint time, before vitest runs.
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['**/components/common/*', '**/components/buttons/*'],
              message:
                'Legacy primitives in components/common/ and components/buttons/ were retired in M002/S12. Use components/ui/* (S08 design system) or the relocated homes (forms/, cars/, images/, filters/, tables/, routes/, shell/) instead.',
            },
          ],
        },
      ],
    },
  }),
  // `vi.importActual<typeof import('./mod')>()` is vitest's documented way to
  // type a partial mock, and an inline `import()` type is the only spelling of
  // it. The shared base bans those in favour of top level type imports, which
  // is right for application code and impossible here, so the rule is relaxed
  // for test files only.
  {
    files: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    rules: {
      '@typescript-eslint/consistent-type-imports': [
        'error',
        {
          prefer: 'type-imports',
          fixStyle: 'inline-type-imports',
          disallowTypeAnnotations: false,
        },
      ],
    },
  },
];
