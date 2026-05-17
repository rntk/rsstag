/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
const config = {
  packageManager: 'npm',
  reporters: ['html', 'clear-text', 'progress', 'json'],
  testRunner: 'command',
  commandRunner: {
    command: 'node --loader ./test/es-module-loader.mjs --test test/*.test.js'
  },
  coverageAnalysis: 'off',
  concurrency: 1,
  // Files without setInterval/long-running mutations
  mutate: [
    'libs/event_system.js',
    'libs/chart-utils.js',
    'storages/progressbar-storage.js',
    'storages/tag-contexts-classification-storage.js',
    'storages/topics-texts-storage.js',
    'storages/wordtree-storage.js',
  ],
  ignorePatterns: [
    'coverage/**',
    'reports/**',
    'node_modules/**',
    'bundle.js',
    'bundle.js.map',
    'quality-report.json',
    'QUALITY_REPORT.md'
  ],
  thresholds: {
    high: 80,
    low: 60,
    break: null
  }
};
export default config;
