const js = require('@eslint/js');
const react = require('eslint-plugin-react');
const reactHooks = require('eslint-plugin-react-hooks');
const prettier = require('eslint-config-prettier');

const browserGlobals = {
  URL: 'readonly',
  alert: 'readonly',
  clearInterval: 'readonly',
  clearTimeout: 'readonly',
  console: 'readonly',
  document: 'readonly',
  fetch: 'readonly',
  FormData: 'readonly',
  navigator: 'readonly',
  setInterval: 'readonly',
  setTimeout: 'readonly',
  window: 'readonly',
};

const nodeGlobals = {
  __dirname: 'readonly',
  console: 'readonly',
  module: 'readonly',
  process: 'readonly',
  require: 'readonly',
};

const testGlobals = {
  ...browserGlobals,
  afterEach: 'readonly',
  beforeEach: 'readonly',
};

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
      'libs/cloud.min.js',
      '../css/*.map',
      '../vis-dist/**',
      '../node_modules/',
      '*.md',
      'package-lock.json',
    ],
  },
  js.configs.recommended,
  {
    files: ['webpack.config.cjs', 'webpack.dev.config.cjs', 'eslint.config.cjs', 'vitest.config.cjs'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'commonjs',
      globals: nodeGlobals,
    },
  },
  {
    files: [
      'components/context-filter-bar.js',
      'components/load-posts.js',
      'components/post-item.js',
      'components/posts-list.js',
      'storages/context-filter-storage.js',
      'storages/posts-storage.js',
      'libs/rsstag_utils.js',
    ],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: browserGlobals,
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
      'react/no-deprecated': 'off',
      'react/prop-types': 'off',
      'react/react-in-jsx-scope': 'off',
    },
  },
  {
    files: ['topics-list.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: browserGlobals,
    },
  },
  {
    files: ['provider-feeds.js', 'tag-feeds.js', 'post-grouped-snippets.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'script',
      globals: browserGlobals,
    },
  },
  {
    files: ['test/**/*.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: testGlobals,
    },
  },
  prettier,
];
