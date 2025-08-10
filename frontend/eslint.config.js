import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

import reactX from 'eslint-plugin-react-x';
import reactDom from 'eslint-plugin-react-dom';
import eslintConfigPrettier from 'eslint-config-prettier'; // Import eslint-config-prettier

export default tseslint.config(
  {
    ignores: ['dist/', 'node_modules/', '*.config.js'],
  },
  // Base config for non-type-checked files
  {
    files: ['*.config.ts', 'vite.config.ts'],
    extends: [...tseslint.configs.recommended],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
    rules: {
      '@typescript-eslint/no-unused-vars': 'warn',
    },
  },
  // Main application files with full type checking
  {
    files: ['src/**/*.ts', 'src/**/*.tsx'],
    extends: [...tseslint.configs.recommendedTypeChecked],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
      parserOptions: {
        project: ['./tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'react-refresh': reactRefresh,
      'react-hooks': reactHooks,
      // Add the react-x and react-dom plugins
      'react-x': reactX,
      'react-dom': reactDom,
    },
    rules: {
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // Enable its recommended typescript rules
      ...reactX.configs['recommended-typescript'].rules,
      ...reactDom.configs.recommended.rules,
      // Disable React 19 warnings for now since we're not using React 19
      'react-x/no-use-context': 'off',
      'react-x/no-context-provider': 'off',
    },
  },
  // Test files with relaxed type checking
  {
    files: ['src/test/**/*.ts', 'src/test/**/*.tsx'],
    extends: [...tseslint.configs.recommended],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
    },
    rules: {
      '@typescript-eslint/no-unsafe-assignment': 'off',
      '@typescript-eslint/no-unsafe-call': 'off',
      '@typescript-eslint/no-unsafe-return': 'off',
      '@typescript-eslint/no-unsafe-member-access': 'off',
      '@typescript-eslint/no-unused-vars': 'warn',
    },
  },
  eslintConfigPrettier // Add this last
);