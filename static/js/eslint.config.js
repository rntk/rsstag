const js = require('@eslint/js');
const react = require('eslint-plugin-react');
const reactHooks = require('eslint-plugin-react-hooks');
const prettier = require('eslint-config-prettier');

module.exports = [
  {
    ignores: [
      'node_modules/',
      'bundle.js',
      'bundle.js.map',
      'bundle.js.LICENSE.txt',
      'Chart.min.js',
      'd3.v6.min.js',
      'google-charts.js',
      '../css/*.map',
      'libs/cloud.min.js',
      '../vis-dist/**',
      '../node_modules/',
      'package-lock.json',
      'package.json',
      '.prettierrc.json',
      'eslint.config.js',
      '*.md',
    ],
  },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      react,
      'react-hooks': reactHooks,
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
    },
  },
  prettier,
];
