import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

// ============================================================
// Helpers
// ============================================================

const source = fs.readFileSync(new URL('../components/ClustersTopics.js', import.meta.url), 'utf8');

// ============================================================
// Section 1: Component Structure
// ============================================================

test('ClustersTopics is declared as a default-exported function', () => {
  assert.ok(
    /const\s+ClustersTopics\s*=\s*\(\s*\)\s*=>/.test(source),
    'ClustersTopics should be an arrow function component'
  );
  assert.ok(
    /export default ClustersTopics/.test(source),
    'ClustersTopics should be default exported'
  );
});

test('ClustersTopics uses React hooks', () => {
  assert.ok(/useState/.test(source), 'should use useState');
  assert.ok(/useEffect/.test(source), 'should use useEffect');
  assert.ok(/useCallback/.test(source), 'should use useCallback');
  assert.ok(/useRef/.test(source), 'should use useRef');
  assert.ok(/useMemo/.test(source), 'should use useMemo');
});

// ============================================================
// Section 2: Data Loading
// ============================================================

test('ClustersTopics loads clusters from window.cluster_data', () => {
  assert.ok(/window\.cluster_data/.test(source), 'component should reference window.cluster_data');
  assert.ok(
    /clusters:\s*window\.cluster_data/.test(source),
    'should assign window.cluster_data to clusters state'
  );
});

test('ClustersTopics clusters are sorted by count descending', () => {
  assert.ok(
    /clusterIds.*sort/.test(source) || /\.sort\(.*clusters\[.*\]\.count/.test(source),
    'clusterIds should be sorted by count'
  );
  assert.ok(
    /clusters\[b\]\.count\s*-\s*clusters\[a\]\.count/.test(source),
    'sort should be descending (b.count - a.count)'
  );
});

// ============================================================
// Section 3: Cluster Click / Fetch Behavior
// ============================================================

test('ClustersTopics fetchSentences calls correct API endpoint', () => {
  assert.ok(
    /fetch_sentences:\s*['"]\/clusters-topics-dyn-sentences['"]/.test(source),
    'should define fetch_sentences URL'
  );
  assert.ok(/URLS\.fetch_sentences/.test(source), 'should use URLS.fetch_sentences');
  assert.ok(/method:\s*['"]POST['"]/.test(source), 'fetch should use POST method');
});

test('ClustersTopics fetchSentences sends ranges in request body', () => {
  assert.ok(
    /JSON\.stringify\(\s*\{\s*ranges:\s*cluster\.ranges/.test(source),
    'should send cluster.ranges in request body'
  );
  assert.ok(/Content-Type.*application\/json/.test(source), 'should set Content-Type header');
});

test('ClustersTopics handles cluster with no ranges', () => {
  assert.ok(
    /!cluster\s*\|\|\s*!cluster\.ranges/.test(source),
    'should check for missing cluster or ranges'
  );
  assert.ok(/ranges:\s*\[\]/.test(source), 'should set empty ranges when no data');
});

// ============================================================
// Section 4: Abort Controller / Cleanup
// ============================================================

test('ClustersTopics uses AbortController for fetch cancellation', () => {
  assert.ok(/abortControllerRef/.test(source), 'should have abortControllerRef');
  assert.ok(/AbortController/.test(source), 'should create AbortController');
  assert.ok(/\.abort\(\)/.test(source), 'should abort previous requests');
  assert.ok(
    /signal:\s*abortControllerRef\.current\.signal/.test(source),
    'should pass abort signal to fetch'
  );
});

test('ClustersTopics cleans up abort controller on unmount', () => {
  assert.ok(
    /useEffect.*abortControllerRef.*abort/.test(source) ||
      /return.*=>.*\{[\s\S]*abortControllerRef[\s\S]*abort/.test(source),
    'should abort controller on unmount'
  );
});

// ============================================================
// Section 5: Read/Unread Actions
// ============================================================

test('ClustersTopics defines changeSnippetsStatus for toggling read state', () => {
  assert.ok(/changeSnippetsStatus/.test(source), 'should define changeSnippetsStatus');
  assert.ok(
    /read_snippets:\s*['"]\/read\/snippets['"]/.test(source),
    'should define read_snippets URL'
  );
  assert.ok(/readed:\s*readed/.test(source), 'should send readed flag in payload');
});

test('ClustersTopics handleToggleRead builds correct selection payload', () => {
  assert.ok(/handleToggleRead/.test(source), 'should define handleToggleRead');
  assert.ok(/postId:\s*range\.post_id/.test(source), 'should include postId in selection');
  assert.ok(
    /sentenceIndices:\s*range\.sentence_indices/.test(source),
    'should include sentenceIndices in selection'
  );
  assert.ok(/rangeKey:\s*rangeKey/.test(source), 'should include rangeKey in selection');
});

test('ClustersTopics handleReadAll sends all selections', () => {
  assert.ok(/handleReadAll/.test(source), 'should define handleReadAll');
  assert.ok(/state\.ranges\.map/.test(source), 'should map all ranges to selections');
});

// ============================================================
// Section 6: buildRangeKey Function
// ============================================================

test('buildRangeKey generates keys from postId and sentenceIndices', () => {
  assert.ok(
    /buildRangeKey\s*=\s*useCallback/.test(source),
    'buildRangeKey should be defined with useCallback'
  );
  assert.ok(/String\(postId\)/.test(source), 'should convert postId to string');
  assert.ok(
    /!sentenceIndices\s*\|\|\s*!sentenceIndices\.length/.test(source) ||
      /!sentenceIndices/.test(source),
    'should check for empty sentenceIndices'
  );
  assert.ok(
    /sentenceIndices\.join\(\s*['"]_['"]\s*\)/.test(source),
    'should join sentenceIndices with underscore'
  );
  assert.ok(/base\s*\+\s*['"]_['"]/.test(source), 'should concatenate base with underscore');
});

// ============================================================
// Section 7: JSX Structure / Rendering
// ============================================================

test('ClustersTopics renders main container div with correct class', () => {
  assert.ok(
    /className="clusters-topics-page"/.test(source),
    'should have clusters-topics-page container'
  );
});

test('ClustersTopics shows "No clusters" when empty', () => {
  assert.ok(/clusterIds\.length\s*===\s*0/.test(source), 'should check if clusterIds is empty');
  assert.ok(/>No clusters</.test(source), 'should show "No clusters" text');
});

test('ClustersTopics renders cluster list with buttons', () => {
  assert.ok(
    /className="clusters-topics-list"/.test(source),
    'should have clusters-topics-list container'
  );
  assert.ok(
    /className={`clusters-topic-item/.test(source) || /className="clusters-topic-item/.test(source),
    'should render clusters-topic-item buttons'
  );
  assert.ok(/is-active/.test(source), 'should support is-active class for selected cluster');
});

test('ClustersTopics displays cluster title and count', () => {
  assert.ok(/className="clusters-topic-title"/.test(source), 'should have title span');
  assert.ok(/className="clusters-topic-count"/.test(source), 'should have count span');
  assert.ok(
    /dangerouslySetInnerHTML.*clusters\[id\]\.title/.test(source),
    'should render cluster title with dangerouslySetInnerHTML'
  );
  assert.ok(/clusters\[id\]\.count/.test(source), 'should render cluster count');
});

test('ClustersTopics renders sentences panel', () => {
  assert.ok(
    /id="clusters-topic-sentences"/.test(source),
    'should have sentences panel with correct id'
  );
  assert.ok(
    /className={`clusters-topic-sentences.*isLoading/.test(source) || /is-loading/.test(source),
    'should apply is-loading class when loading'
  );
});

test('ClustersTopics shows placeholder when no cluster selected', () => {
  assert.ok(/!currentClusterId/.test(source), 'should check if no cluster is selected');
  assert.ok(/className="clusters-topic-placeholder"/.test(source), 'should render placeholder');
  assert.ok(
    /Select a cluster to load sentences/.test(source),
    'should show select cluster placeholder text'
  );
});

test('ClustersTopics renders cluster header for selected cluster', () => {
  assert.ok(/className="clusters-topic-header"/.test(source), 'should have header div');
  assert.ok(/currentCluster.*title/.test(source), 'should show current cluster title in header');
});

// ============================================================
// Section 8: Sentence Display
// ============================================================

test('ClustersTopics renders sentences list container', () => {
  assert.ok(
    /className="clusters-topic-sentences-list"/.test(source),
    'should have sentences list container'
  );
});

test('ClustersTopics sentence rows have read/unread classes', () => {
  assert.ok(
    /className={`clusters-topic-sentence.*isRead/.test(source) || /is-read/.test(source),
    'should apply read/unread classes'
  );
  assert.ok(
    /is-read/.test(source) && /is-unread/.test(source),
    'should have both is-read and is-unread classes'
  );
});

test('ClustersTopics sentence row shows toggle read button', () => {
  assert.ok(
    /className="clusters-topic-toggle-read"/.test(source),
    'should have toggle read button'
  );
  assert.ok(/'Mark Read'/.test(source), 'should show "Mark Read" text');
  assert.ok(/'Mark Unread'/.test(source), 'should show "Mark Unread" text');
  assert.ok(
    /Mark as read/.test(source) || /Mark as unread/.test(source),
    'should have appropriate title tooltip'
  );
});

test('ClustersTopics sentence row contains post link', () => {
  assert.ok(/className="clusters-topic-sentence-link"/.test(source), 'should have link class');
  assert.ok(
    /href={`\/posts\/\$\{encodeURIComponent\(range\.post_id\)\}`}/.test(source) ||
      /href=.*\/posts\/.*range\.post_id/.test(source),
    'should link to /posts/{post_id}'
  );
});

test('ClustersTopics sentence shows meta with topic_title', () => {
  assert.ok(/className="clusters-topic-sentence-meta"/.test(source), 'should have meta div');
  assert.ok(/range\.topic_title/.test(source), 'should show topic_title when available');
});

test('ClustersTopics sentence shows post_id in meta', () => {
  assert.ok(/range\.post_id/.test(source), 'should display post_id in meta');
});

// ============================================================
// Section 9: Toolbar
// ============================================================

test('ClustersTopics toolbar has Read all and Unread all buttons', () => {
  assert.ok(/className="clusters-topic-toolbar"/.test(source), 'should have toolbar container');
  assert.ok(/Read all/.test(source), 'should have Read all button');
  assert.ok(/Unread all/.test(source), 'should have Unread all button');
  assert.ok(/className="clusters-read-btn"/.test(source), 'should use clusters-read-btn class');
});

// ============================================================
// Section 10: Error Handling
// ============================================================

test('ClustersTopics handles fetch errors with .catch', () => {
  assert.ok(/\.catch\(\(err\)\s*=>/.test(source), 'should have catch handler for fetch errors');
  assert.ok(/console\.error.*Failed to fetch sentences/.test(source), 'should log fetch errors');
  assert.ok(/AbortError/.test(source), 'should handle AbortError separately');
});

test('ClustersTopics handles status update errors', () => {
  assert.ok(
    /console\.error.*Failed to update snippet status/.test(source),
    'should log status update errors'
  );
  assert.ok(
    /alert.*Failed to update snippet status/.test(source),
    'should alert on status update failure'
  );
});

// ============================================================
// Section 11: Data Validation
// ============================================================

test('ClustersTopics changeSnippetsStatus guards against empty selections', () => {
  assert.ok(
    /!selections\s*\|\|\s*!selections\.length/.test(source),
    'should return early for empty selections'
  );
});

test('ClustersTopics handles missing sentence_indices in buildRangeKey', () => {
  assert.ok(
    /!sentenceIndices\s*\|\|\s*!sentenceIndices\.length/.test(source),
    'should handle undefined or empty sentenceIndices'
  );
});
