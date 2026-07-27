const fs = require('node:fs');
const path = require('node:path');

/**
 * Suites written against vitest.
 *
 * Most of ./test targets Node's built-in runner (`npm test`), which cannot load
 * a file importing vitest -- and vitest cannot load one importing node:test.
 * The two sets are told apart by the import each file actually uses, so a new
 * suite lands in the right runner without following a naming convention.
 *
 * @returns {string[]}
 */
function vitestSuites() {
  const testDir = path.join(__dirname, 'test');
  return fs
    .readdirSync(testDir)
    .filter((name) => name.endsWith('.test.js') || name.endsWith('.spec.js'))
    .filter((name) =>
      /from\s+['"]vitest['"]/.test(fs.readFileSync(path.join(testDir, name), 'utf8'))
    )
    .map((name) => `test/${name}`);
}

module.exports = {
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test/setup.js'],
    include: vitestSuites(),
  },
};
