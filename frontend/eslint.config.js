import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import reactX from 'eslint-plugin-react-x';
import reactDom from 'eslint-plugin-react-dom';
import { reactConfig } from '@webbpulse/eslint-config/react';

export default [
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
      'react-x/no-use-context': 'off',
      'react-x/no-context-provider': 'off',
      'react-x/unsupported-syntax': 'off',
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
