import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'post-bigrams.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Export and function tests
// ============================================================

test('source exports named PostsBigrams function', () => {
  const src = readSource();
  assert.ok(/export function PostsBigrams/.test(src),
    'should export PostsBigrams function');
});

test('PostsBigrams accepts state parameter', () => {
  const src = readSource();
  assert.ok(/function PostsBigrams\s*\(\s*state\s*\)/.test(src),
    'should accept state parameter');
});

// ============================================================
// Guard and edge case tests
// ============================================================

test('source checks for falsy state', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*!\s*state/.test(src),
    'should check for falsy state');
});

test('source checks for missing posts', () => {
  const src = readSource();
  assert.ok(/!\s*state\.posts/.test(src),
    'should check for state.posts');
});

test('returns "No posts" when state is invalid', () => {
  const src = readSource();
  assert.ok(/<p>No posts<\/p>/.test(src),
    'should return <p>No posts</p>');
});

// ============================================================
// Bigram extraction tests
// ============================================================

test('source iterates over state.posts', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let\s+item\s+of\s+state\.posts/.test(src),
    'should iterate over state.posts');
});

test('source extracts post from item tuple', () => {
  const src = readSource();
  assert.ok(/item\[1\]/.test(src),
    'should access item[1] for post data');
});

test('source collects post.tags frequencies', () => {
  const src = readSource();
  assert.ok(/post\.post\.tags/.test(src),
    'should access post.post.tags');
});

test('source collects post.bi_grams frequencies', () => {
  const src = readSource();
  assert.ok(/post\.post\.bi_grams/.test(src),
    'should access post.post.bi_grams');
});

test('source uses bi_grams object for counting', () => {
  const src = readSource();
  assert.ok(/bi_grams\s*\[\s*bi\s*\]/.test(src),
    'should count bigrams in bi_grams object');
});

test('source uses freq object for tag frequency', () => {
  const src = readSource();
  assert.ok(/freq\s*\[\s*tag\s*\]/.test(src),
    'should track tag frequencies');
});

// ============================================================
// Stopword filtering tests
// ============================================================

test('source imports stopwords', () => {
  const src = readSource();
  assert.ok(/import.*stopwords.*from/.test(src),
    'should import stopwords');
});

test('source creates stopwords instance', () => {
  const src = readSource();
  assert.ok(/stopwords\s*\(\s*\)/.test(src),
    'should call stopwords()');
});

test('source splits bigram into words for stopword check', () => {
  const src = readSource();
  assert.ok(/bi\.split\s*\(\s*['"] ['"]/.test(src),
    'should split bigram by space');
});

test('source checks first word against stopwords', () => {
  const src = readSource();
  assert.ok(/stopw\.has\s*\(\s*tags\[0\]/.test(src),
    'should check first word against stopwords');
});

test('source checks second word against stopwords', () => {
  const src = readSource();
  assert.ok(/stopw\.has\s*\(\s*tags\[1\]/.test(src),
    'should check second word against stopwords');
});

test('source continues loop when stopword found', () => {
  const src = readSource();
  assert.ok(/continue/.test(src),
    'should skip bigrams with stopwords');
});

// ============================================================
// Coefficient and sorting tests
// ============================================================

test('source calculates coefficient for ranking', () => {
  const src = readSource();
  assert.ok(/coef/.test(src),
    'should define coef variable');
});

test('source uses bigram count in coefficient', () => {
  const src = readSource();
  assert.ok(/bi_grams\s*\[\s*bi\s*\]/.test(src),
    'should use bigram count in coef');
});

test('source divides by tag frequency in coefficient', () => {
  const src = readSource();
  assert.ok(/bi_grams\s*\[\s*bi\s*\]\s*\/\s*freq/.test(src),
    'should divide bigram count by tag frequency');
});

test('source adds tag frequency to coefficient', () => {
  const src = readSource();
  assert.ok(/\+\s*freq\s*\[\s*tags\[1\]\]/.test(src),
    'should add second tag frequency');
});

test('source sorts bigrams_l descending', () => {
  const src = readSource();
  assert.ok(/bi_grams_l\.sort/.test(src),
    'should sort bi_grams_l');
});

test('source uses a[2] and b[2] for coefficient comparison', () => {
  const src = readSource();
  assert.ok(/a\[2\]/.test(src) && /b\[2\]/.test(src),
    'should compare coef values at index 2');
});

test('source returns 1 when a[2] < b[2] for descending sort', () => {
  const src = readSource();
  assert.ok(/a\[2\]\s*<\s*b\[2\]/.test(src),
    'should sort descending by coef');
});

// ============================================================
// Filtering by count tests
// ============================================================

test('source filters bigrams with count >= 2', () => {
  const src = readSource();
  assert.ok(/bi\[1\]\s*<\s*2/.test(src),
    'should check if bigram count < 2');
  assert.ok(/continue/.test(src),
    'should skip bigrams with count < 2');
});

// ============================================================
// Tag object construction tests
// ============================================================

test('source creates tag object with tag property', () => {
  const src = readSource();
  assert.ok(/tag\s*:\s*bi\[0\]/.test(src),
    'should set tag from bigram string');
});

test('source sets count on tag object', () => {
  const src = readSource();
  assert.ok(/count\s*:\s*bi\[1\]/.test(src),
    'should set count from bigram count');
});

test('source splits bigram into words array', () => {
  const src = readSource();
  assert.ok(/words\s*:\s*bi\[0\]\.split/.test(src),
    'should create words array from bigram');
});

test('source creates URL with /bi-gram/ path', () => {
  const src = readSource();
  assert.ok(/['"]\/bi-gram\//.test(src),
    'should use /bi-gram/ path');
});

test('source URL-encodes bigram in URL', () => {
  const src = readSource();
  assert.ok(/encodeURIComponent/.test(src),
    'should use encodeURIComponent');
});

// ============================================================
// TagItem rendering tests
// ============================================================

test('source imports TagItem', () => {
  const src = readSource();
  assert.ok(/import TagItem from/.test(src),
    'should import TagItem');
});

test('source renders TagItem components', () => {
  const src = readSource();
  assert.ok(/<TagItem/.test(src),
    'should render TagItem elements');
});

test('source passes is_bigram={true} to TagItem', () => {
  const src = readSource();
  assert.ok(/is_bigram\s*=\s*\{\s*true\s*\}/.test(src),
    'should set is_bigram={true}');
});

test('source passes tags={[]} to TagItem', () => {
  const src = readSource();
  assert.ok(/tags\s*=\s*\{\s*\[\s*\]\s*\}/.test(src),
    'should set tags to empty array');
});

test('source passes tag_hash to TagItem', () => {
  const src = readSource();
  assert.ok(/tag_hash\s*=\s*\{?\s*bi\[0\]/.test(src),
    'should pass bigram as tag_hash');
});

test('source passes uniq_id to TagItem', () => {
  const src = readSource();
  assert.ok(/uniq_id\s*=\s*\{?\s*bi\[0\]/.test(src),
    'should pass bigram as uniq_id');
});

test('source uses key with bigram and count', () => {
  const src = readSource();
  assert.ok(/key\s*=\s*\{?\s*bi\[0\]\s*\+\s*bi\[1\]/.test(src),
    'should use bigram+count as key');
});

// ============================================================
// Render structure tests
// ============================================================

test('source uses posts_list CSS class', () => {
  const src = readSource();
  assert.ok(/posts_list/.test(src),
    'should use posts_list CSS class');
});

test('source uses cloud CSS class', () => {
  const src = readSource();
  assert.ok(/['"]cloud['"]/.test(src),
    'should use cloud CSS class');
});

test('source uses ol element for tag list', () => {
  const src = readSource();
  assert.ok(/<ol/.test(src),
    'should use ol element');
});

test('source wraps in div.posts container', () => {
  const src = readSource();
  assert.ok(/className\s*=\s*['"]posts['"]/.test(src),
    'should use posts CSS class');
});
