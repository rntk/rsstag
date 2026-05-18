/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
const config = {
  packageManager: 'npm',
  reporters: ['html', 'clear-text', 'progress', 'json'],
  testRunner: 'command',
  commandRunner: {
    command: 'sh -c \'node --loader ./test/es-module-loader.mjs --test $(find ./test -type f \\( -name "*.test.js" -o -name "*.spec.js" \\) | sort)\''
  },
  coverageAnalysis: 'off',
  concurrency: 1,
  // Source files with import-based tests (compatible with stryker instrumentation).
  // Files using readFileSync source-scanning (all components, top-level page files,
  // render-helper) are intentionally excluded because stryker wraps string literals
  // with mutant tracking code, breaking regex-based source pattern matching.
  mutate: [
    'storages/**/*.js',
    'libs/chart-utils.js',
    'libs/event_system.js',
    'libs/rsstag_utils.js',
    'libs/stopwords.js',
  ],
  ignorePatterns: [
    'coverage/**',
    'coverage-check/**',
    '.c8-temp/**',
    '.c8-temp-check/**',
    'reports/**',
    'node_modules/**',
    'bundle.js',
    'bundle.js.map',
    'libs/cloud.min.js',
    'google-charts.js',
    'Chart.min.js',
    'd3.v6.min.js',
    'quality-report.json',
    'QUALITY_REPORT.md'
  ],
  thresholds: {
    high: 80,
    low: 60,
    break: 80
  }
};
export default config;
