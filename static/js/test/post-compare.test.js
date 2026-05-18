import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'post-compare.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// Class structure tests
// ============================================================

test('source declares PostComparePage as a default export class', () => {
  assert.ok(/export\s+default\s+class\s+PostComparePage\s+extends\s+PostGroupedPage/.test(source), 'should export default class PostComparePage extends PostGroupedPage');
});

test('source imports PostGroupedPage', () => {
  assert.ok(/import\s+PostGroupedPage\s+from\s+['"]\.\/post-grouped\.js['"]/.test(source), 'should import PostGroupedPage from post-grouped.js');
});

test('source declares constructor calling super()', () => {
  assert.ok(/constructor\s*\(\s*\)\s*\{[\s\S]*super\(\)/.test(source), 'constructor should call super()');
});

// ============================================================
// Constructor state tests
// ============================================================

test('source sets currentTopic to null in constructor', () => {
  assert.ok(/this\.currentTopic\s*=\s*null/.test(source), 'currentTopic should be null');
});

test('source sets anchorRatio to 0.3', () => {
  assert.ok(/this\.anchorRatio\s*=\s*0\.3/.test(source), 'anchorRatio should be 0.3');
});

test('source sets syncScroll to false', () => {
  assert.ok(/this\.syncScroll\s*=\s*false/.test(source), 'syncScroll should be false');
});

test('source sets isSyncingScroll to false', () => {
  assert.ok(/this\.isSyncingScroll\s*=\s*false/.test(source), 'isSyncingScroll should be false');
});

// ============================================================
// Method declarations tests
// ============================================================

test('source declares init method', () => {
  assert.ok(/\binit\s*\(\s*\)/.test(source), 'should have init method');
});

test('source declares initSyncScrollToggle method', () => {
  assert.ok(/\binitSyncScrollToggle\s*\(\s*\)/.test(source), 'should have initSyncScrollToggle method');
});

test('source declares attachScrollSync method', () => {
  assert.ok(/\battachScrollSync\s*\(\s*\)/.test(source), 'should have attachScrollSync method');
});

test('source declares attachHeaderToggleHandlers method', () => {
  assert.ok(/\battachHeaderToggleHandlers\s*\(\s*\)/.test(source), 'should have attachHeaderToggleHandlers method');
});

test('source declares buildPostsList method', () => {
  assert.ok(/\bbuildPostsList\s*\(\s*\)/.test(source), 'should have buildPostsList method');
});

test('source declares handleTopicSelection method', () => {
  assert.ok(/\bhandleTopicSelection\s*\(\s*topicPath\s*\)/.test(source), 'should have handleTopicSelection method');
});

test('source declares activateInitialTopic method', () => {
  assert.ok(/\bactivateInitialTopic\s*\(\s*\)/.test(source), 'should have activateInitialTopic method');
});

test('source declares clearCompareState method', () => {
  assert.ok(/\bclearCompareState\s*\(\s*\)/.test(source), 'should have clearCompareState method');
});

test('source declares syncTopicColumns method', () => {
  assert.ok(/\bsyncTopicColumns\s*\(\s*topicPath\s*\)/.test(source), 'should have syncTopicColumns method');
});

// ============================================================
// init method structure tests
// ============================================================

test('init calls stripGlobalStyles', () => {
  assert.ok(/this\.stripGlobalStyles\(\)/.test(source), 'init should call stripGlobalStyles');
});

test('init calls setupPostSections', () => {
  assert.ok(/this\.setupPostSections\(\)/.test(source), 'init should call setupPostSections');
});

test('init calls indexSentences', () => {
  assert.ok(/this\.indexSentences\(\)/.test(source), 'init should call indexSentences');
});

test('init sets isContentReady to true', () => {
  assert.ok(/this\.isContentReady\s*=\s*true/.test(source), 'should set isContentReady to true');
});

test('init calls buildTopicsList', () => {
  assert.ok(/this\.buildTopicsList\(\)/.test(source), 'init should call buildTopicsList');
});

test('init calls buildPostsList', () => {
  assert.ok(/this\.buildPostsList\(\)/.test(source), 'init should call buildPostsList');
});

test('init calls attachSentenceGroupHandlers', () => {
  assert.ok(/this\.attachSentenceGroupHandlers\(\)/.test(source), 'init should call attachSentenceGroupHandlers');
});

test('init calls attachHeaderToggleHandlers', () => {
  assert.ok(/this\.attachHeaderToggleHandlers\(\)/.test(source), 'init should call attachHeaderToggleHandlers');
});

test('init calls setInitialReadStatus', () => {
  assert.ok(/this\.setInitialReadStatus\(\)/.test(source), 'init should call setInitialReadStatus');
});

test('init calls bindGlobalEvents', () => {
  assert.ok(/this\.bindGlobalEvents\(\)/.test(source), 'init should call bindGlobalEvents');
});

test('init calls activateInitialTopic', () => {
  assert.ok(/this\.activateInitialTopic\(\)/.test(source), 'init should call activateInitialTopic');
});

test('init calls initSyncScrollToggle', () => {
  assert.ok(/this\.initSyncScrollToggle\(\)/.test(source), 'init should call initSyncScrollToggle');
});

test('init calls attachScrollSync', () => {
  assert.ok(/this\.attachScrollSync\(\)/.test(source), 'init should call attachScrollSync');
});

// ============================================================
// initSyncScrollToggle tests
// ============================================================

test('initSyncScrollToggle queries #sync_scroll_toggle', () => {
  assert.ok(/document\.getElementById\s*\(\s*['"]sync_scroll_toggle['"]\s*\)/.test(source), 'should get sync_scroll_toggle by ID');
});

test('initSyncScrollToggle returns early if button not found', () => {
  assert.ok(/if\s*\(!btn\)\s*\{[\s\S]*return/.test(source), 'should return early if btn is null');
});

test('initSyncScrollToggle adds click handler to button', () => {
  assert.ok(/btn\.addEventListener\s*\(\s*['"]click['"]/.test(source), 'should add click listener');
});

test('initSyncScrollToggle toggles syncScroll state', () => {
  assert.ok(/this\.syncScroll\s*=\s*!this\.syncScroll/.test(source), 'should toggle syncScroll');
});

test('initSyncScrollToggle toggles active class on button', () => {
  assert.ok(/btn\.classList\.toggle\s*\(\s*['"]active['"]\s*,\s*this\.syncScroll\s*\)/.test(source), 'should toggle active class');
});

test('initSyncScrollToggle updates button text for Synced/Independent', () => {
  assert.ok(/['"]Scroll:\s*Synced['"]/.test(source), 'should show "Scroll: Synced"');
  assert.ok(/['"]Scroll:\s*Independent['"]/.test(source), 'should show "Scroll: Independent"');
});

// ============================================================
// attachScrollSync tests
// ============================================================

test('attachScrollSync queries .compare-post-body elements', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.compare-post-body['"]\s*\)/.test(source), 'should query .compare-post-body');
});

test('attachScrollSync returns early if fewer than 2 bodies', () => {
  assert.ok(/bodies\.length\s*<\s*2/.test(source), 'should check for at least 2 bodies');
});

test('attachScrollSync uses scroll ratio for sync', () => {
  assert.ok(/source\.scrollTop\s*\/\s*maxScroll/.test(source), 'should use scrollTop ratio');
});

test('attachScrollSync uses scrollTo with instant behavior', () => {
  assert.ok(/behavior\s*:\s*['"]instant['"]/.test(source), 'should use instant scroll behavior');
});

test('attachScrollSync uses guard timer with isSyncingScroll flag', () => {
  assert.ok(/this\.isSyncingScroll\s*=\s*true/.test(source), 'should set isSyncingScroll true');
  assert.ok(/this\.isSyncingScroll\s*=\s*false/.test(source), 'should set isSyncingScroll false');
});

test('attachScrollSync uses setTimeout with 180ms debounce', () => {
  assert.ok(/setTimeout[\s\S]*180/.test(source), 'should use 180ms debounce');
});

test('attachScrollSync uses 150ms guard timer', () => {
  assert.ok(/150/.test(source), 'should use 150ms guard timer');
});

// ============================================================
// attachHeaderToggleHandlers tests
// ============================================================

test('attachHeaderToggleHandlers queries .compare-post-header', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.compare-post-header['"]\s*\)/.test(source), 'should query .compare-post-header');
});

test('attachHeaderToggleHandlers queries .compare-header-toggle inside header', () => {
  assert.ok(/header\.querySelector\s*\(\s*['"]\.compare-header-toggle['"]\s*\)/.test(source), 'should query toggle inside header');
});

test('attachHeaderToggleHandlers returns early if toggle not found', () => {
  assert.ok(/if\s*\(!toggle\)\s*\{[\s\S]*return/.test(source), 'should return if no toggle');
});

test('attachHeaderToggleHandlers reads data-header-state attribute', () => {
  assert.ok(/header\.getAttribute\s*\(\s*['"]data-header-state['"]\s*\)/.test(source), 'should read data-header-state');
});

test('attachHeaderToggleHandlers toggles between expanded and collapsed', () => {
  assert.ok(/['"]collapsed['"]/.test(source), 'should handle collapsed state');
  assert.ok(/['"]expanded['"]/.test(source), 'should handle expanded state');
});

test('attachHeaderToggleHandlers sets aria-expanded attribute', () => {
  assert.ok(/toggle\.setAttribute\s*\(\s*['"]aria-expanded['"]/.test(source), 'should set aria-expanded');
});

// ============================================================
// buildPostsList tests
// ============================================================

test('buildPostsList queries #posts_list and #compare_scroll', () => {
  assert.ok(/document\.getElementById\s*\(\s*['"]posts_list['"]\s*\)/.test(source), 'should get posts_list');
  assert.ok(/document\.getElementById\s*\(\s*['"]compare_scroll['"]\s*\)/.test(source), 'should get compare_scroll');
});

test('buildPostsList returns early if elements or posts are missing', () => {
  assert.ok(/!postsList/.test(source), 'should check postsList');
  assert.ok(/!compareScroll/.test(source), 'should check compare_scroll');
  assert.ok(/window\.posts/.test(source), 'should check window.posts');
});

test('buildPostsList creates div elements with topic-item class', () => {
  assert.ok(/el\.className\s*=\s*['"]topic-item['"]/.test(source), 'should set topic-item class');
});

test('buildPostsList sets background color and border on topic items', () => {
  assert.ok(/'#4285f440'/.test(source), 'should set blue background');
  assert.ok(/borderLeft/.test(source), 'should set blue border');
});

test('buildPostsList shows Post ID and feed title', () => {
  assert.ok(/post\.post_id/.test(source), 'should use post_id');
  assert.ok(/post\.feed_title/.test(source), 'should use feed_title');
  assert.ok(/['"]Unknown['"]/.test(source), 'should fallback to "Unknown"');
});

test('buildPostsList uses data-post-id selector for columns', () => {
  assert.ok(/\[data-post-id=["']\$\{post\.post_id\}["']\]/.test(source), 'should query by data-post-id');
});

test('buildPostsList adds range-highlight and pulse classes on click', () => {
  assert.ok(/['"]range-highlight['"]/.test(source), 'should add range-highlight class');
  assert.ok(/['"]pulse['"]/.test(source), 'should add pulse class');
});

test('buildPostsList uses setTimeout to remove highlight after 1500ms', () => {
  assert.ok(/setTimeout[\s\S]*1500/.test(source), 'should remove highlight after 1500ms');
});

// ============================================================
// handleTopicSelection tests
// ============================================================

test('handleTopicSelection calls setActiveTopic', () => {
  assert.ok(/this\.setActiveTopic\s*\(\s*topicPath\s*\)/.test(source), 'should call setActiveTopic');
});

test('handleTopicSelection resets topic state index to 0', () => {
  assert.ok(/state\.index\s*=\s*0/.test(source), 'should reset index to 0');
});

test('handleTopicSelection sets currentTopic', () => {
  assert.ok(/this\.currentTopic\s*=\s*topicPath/.test(source), 'should set currentTopic');
});

test('handleTopicSelection calls syncTopicColumns', () => {
  assert.ok(/this\.syncTopicColumns\s*\(\s*topicPath\s*\)/.test(source), 'should call syncTopicColumns');
});

// ============================================================
// activateInitialTopic tests
// ============================================================

test('activateInitialTopic reads window.current_topic', () => {
  assert.ok(/window\.current_topic/.test(source), 'should read window.current_topic');
  assert.ok(/typeof\s+window\.current_topic\s*===\s*['"]string['"]/.test(source), 'should check type is string');
});

test('activateInitialTopic falls back to first topicState key', () => {
  assert.ok(/Object\.keys\s*\(\s*this\.topicState/.test(source), 'should fall back to Object.keys');
});

test('activateInitialTopic returns early if no default topic', () => {
  assert.ok(/if\s*\(!defaultTopic\)\s*\{[\s\S]*return/.test(source), 'should return early if no topic');
});

// ============================================================
// clearCompareState tests
// ============================================================

test('clearCompareState queries .compare-post-column', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.compare-post-column['"]\s*\)/.test(source), 'should query compare-post-column');
});

test('clearCompareState removes compare-post-column-no-match class', () => {
  assert.ok(/classList\.remove\s*\(\s*['"]compare-post-column-no-match['"]/.test(source), 'should remove no-match class');
});

test('clearCompareState queries .compare-anchor-sentence', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.compare-anchor-sentence['"]\s*\)/.test(source), 'should query compare-anchor-sentence');
});

// ============================================================
// syncTopicColumns tests
// ============================================================

test('syncTopicColumns reads sentences and color from topicState', () => {
  assert.ok(/topicState\.sentences/.test(source), 'should read sentences from topicState');
  assert.ok(/topicState\.color/.test(source), 'should read color from topicState');
});

test('syncTopicColumns calls highlightSentences', () => {
  assert.ok(/this\.highlightSentences\s*\(\s*sentenceNumbers\s*,\s*color/.test(source), 'should call highlightSentences');
});

test('syncTopicColumns queries .compare-post-column', () => {
  assert.ok(/document\.querySelectorAll\s*\(\s*['"]\.compare-post-column['"]\s*\)/.test(source), 'should query columns');
});

test('syncTopicColumns queries sentence groups by data-sentence attribute', () => {
  assert.ok(/\.sentence-group\[data-sentence=["']\$\{/.test(source), 'should query by data-sentence');
});

test('syncTopicColumns adds compare-post-column-no-match when no anchor found', () => {
  assert.ok(/column\.classList\.add\s*\(\s*['"]compare-post-column-no-match['"]/.test(source), 'should add no-match class');
});

test('syncTopicColumns sets emptyState.hidden to true/false based on match', () => {
  assert.ok(/emptyState\.hidden\s*=\s*false/.test(source), 'should hide empty state when matched');
  assert.ok(/emptyState\.hidden\s*=\s*true/.test(source), 'should show empty state when no match');
});

test('syncTopicColumns adds compare-anchor-sentence class to anchor', () => {
  assert.ok(/span\.classList\.add\s*\(\s*['"]compare-anchor-sentence['"]/.test(source), 'should add anchor class');
});

test('syncTopicColumns scrolls to anchor using anchorRatio', () => {
  assert.ok(/body\.clientHeight\s*\*\s*this\.anchorRatio/.test(source), 'should use anchorRatio for scroll position');
});

test('syncTopicColumns uses smooth scroll behavior', () => {
  assert.ok(/behavior\s*:\s*['"]smooth['"]/.test(source), 'should use smooth scrolling');
});
