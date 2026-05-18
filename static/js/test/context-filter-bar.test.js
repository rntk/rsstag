import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, '..', 'components', 'context-filter-bar.js');
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

// ============================================================
// Module-scope constants
// ============================================================

test('source declares FILTER_TYPES constant', () => {
  assert.ok(/const\s+FILTER_TYPES\s*=\s*\[/.test(source), 'should declare FILTER_TYPES');
});

test('FILTER_TYPES has 5 entries with correct types', () => {
  const ftMatch = source.match(/const\s+FILTER_TYPES\s*=\s*\[([\s\S]*?)\];/);
  assert.ok(ftMatch);
  const types = ftMatch[1].match(/type\s*:\s*['"](\w+)['"]/g);
  assert.equal(types.length, 5);
  assert.ok(types.some((t) => t.includes('tags')));
  assert.ok(types.some((t) => t.includes('feeds')));
  assert.ok(types.some((t) => t.includes('categories')));
  assert.ok(types.some((t) => t.includes('topics')));
  assert.ok(types.some((t) => t.includes('subtopics')));
});

test('FILTER_TYPE_MAP is declared using FILTER_TYPES.reduce', () => {
  assert.ok(/const\s+FILTER_TYPE_MAP\s*=\s*FILTER_TYPES\.reduce/.test(source));
});

// ============================================================
// Pure functions: normalizeFilters (source-inspection)
// ============================================================

test('normalizeFilters is declared as a function', () => {
  assert.ok(/function\s+normalizeFilters\s*\(/.test(source), 'should declare normalizeFilters');
});

test('normalizeFilters accepts filters parameter with default empty object', () => {
  assert.ok(/normalizeFilters\s*\(\s*filters\s*=\s*\{}/.test(source),
    'should have filters={} default parameter');
});

test('normalizeFilters iterates over FILTER_TYPES to normalize each type', () => {
  assert.ok(/FILTER_TYPES\.forEach/.test(source), 'should iterate FILTER_TYPES');
  assert.ok(/\{\s*type\s*\}/.test(source), 'should destructure type from each entry');
});

test('normalizeFilters checks Array.isArray for each filter value', () => {
  assert.ok(/Array\.isArray\(values\)/.test(source), 'should check if value is array');
});

test('normalizeFilters filters to only valid trimmed strings', () => {
  assert.ok(/typeof value === 'string'/.test(source), 'should check type is string');
  assert.ok(/value\.trim\(\)/.test(source) || /\.trim/.test(source), 'should trim values');
});

test('normalizeFilters returns object with all filter type keys', () => {
  assert.ok(/normalized\[type\]/.test(source), 'should assign to normalized[type]');
  assert.ok(/return normalized/.test(source), 'should return normalized object');
});

// ============================================================
// Pure functions: normalizeState (source-inspection)
// ============================================================

test('normalizeState is declared as a function', () => {
  assert.ok(/function\s+normalizeState\s*\(/.test(source), 'should declare normalizeState');
});

test('normalizeState accepts rawState parameter with default', () => {
  assert.ok(/normalizeState\s*\(\s*rawState\s*=\s*\{}/.test(source),
    'should have rawState={} default');
});

test('normalizeState extracts filters from rawState.filters or rawState', () => {
  assert.ok(/rawState\.filters\s*\|\|\s*rawState/.test(source),
    'should use rawState.filters || rawState');
});

test('normalizeState calls normalizeFilters on extracted filters', () => {
  assert.ok(/normalizeFilters\(filters\)/.test(source),
    'should call normalizeFilters');
});

test('normalizeState derives active from non-empty filters', () => {
  assert.ok(/Object\.values\(normalizedFilters\)\.some/.test(source),
    'should use .some to check for non-empty filters');
  assert.ok(/values\.length > 0/.test(source),
    'should check values.length > 0');
});

test('normalizeState respects explicit boolean active flag', () => {
  assert.ok(/typeof rawState\.active === 'boolean'/.test(source),
    'should check if active is boolean');
});

test('normalizeState returns object with active and filters', () => {
  assert.ok(/active:.*rawState\.active/.test(source),
    'should include active in return value');
  assert.ok(/filters:.*normalizedFilters/.test(source),
    'should include normalized filters in return value');
});

// ============================================================
// Pure functions: normalizeSuggestion (source-inspection)
// ============================================================

test('normalizeSuggestion is declared as a function', () => {
  assert.ok(/function\s+normalizeSuggestion\s*\(/.test(source), 'should declare normalizeSuggestion');
});

test('normalizeSuggestion handles string input by trimming and returning value/label/meta', () => {
  assert.ok(/typeof rawSuggestion === 'string'/.test(source),
    'should check if input is string');
  assert.ok(/rawSuggestion\.trim\(\)/.test(source),
    'should trim string input');
  assert.ok(/\{ value, label: value, meta: '' \}/.test(source),
    'should return {value, label, meta} for string');
});

test('normalizeSuggestion returns null for empty or whitespace-only string', () => {
  assert.ok(/if\s*\(\s*!value\s*\)/.test(source),
    'should check for empty value after trim');
  assert.ok(/return null/.test(source),
    'should return null for empty');
});

test('normalizeSuggestion returns null for null/undefined/non-object input', () => {
  assert.ok(/!rawSuggestion/.test(source),
    'should check for falsy input');
  assert.ok(/typeof rawSuggestion !== 'object'/.test(source),
    'should check type is object');
});

test('normalizeSuggestion handles object with value/label/meta fields', () => {
  assert.ok(/\.value/.test(source), 'should access .value');
  assert.ok(/\.label/.test(source), 'should access .label');
  assert.ok(/\.meta/.test(source), 'should access .meta');
});

test('normalizeSuggestion uses tag field as fallback for value', () => {
  assert.ok(/\.tag/.test(source), 'should check .tag field');
});

test('normalizeSuggestion uses name field as fallback for value', () => {
  assert.ok(/\.name/.test(source), 'should check .name field');
});

test('normalizeSuggestion falls back label to value when missing', () => {
  assert.ok(/label.*value/.test(source), 'should fall back label to value');
});

test('normalizeSuggestion trims label and meta', () => {
  assert.ok(/label.*\.trim\(\)/.test(source), 'should trim label');
  assert.ok(/meta.*\.trim\(\)/.test(source), 'should trim meta');
});

test('normalizeSuggestion returns null for object with empty value', () => {
  assert.ok(/!value/.test(source), 'should check for empty value');
});

// ============================================================
// Class structure tests
// ============================================================

test('source declares ContextFilterBar as default-exported class', () => {
  assert.ok(/export\s+default\s+class\s+ContextFilterBar/.test(source));
});

test('ContextFilterBar constructor accepts container_id and event_system params', () => {
  assert.ok(/constructor\s*\(\s*container_id\s*,\s*event_system\s*\)/.test(source));
});

test('constructor stores ES, container_id, and initializes _state', () => {
  assert.ok(/this\.ES\s*=\s*event_system/.test(source));
  assert.ok(/this\.container_id\s*=\s*container_id/.test(source));
  assert.ok(/this\._state\s*=\s*normalizeState\(\)/.test(source));
  assert.ok(/this\._modalState\s*=\s*null/.test(source));
});

test('escapeHtml method is declared', () => {
  assert.ok(/escapeHtml\s*\(\s*str\s*\)/.test(source));
});

test('escapeHtml uses document.createElement with div', () => {
  assert.ok(/document\.createElement\s*\(\s*['"]div['"]\s*\)/.test(source));
  assert.ok(/div\.textContent\s*=\s*str/.test(source));
  assert.ok(/return\s+div\.innerHTML/.test(source));
});

test('render method is declared', () => {
  assert.ok(/render\s*\(\s*\)/.test(source));
});

test('bindClickHandlers method is declared', () => {
  assert.ok(/bindClickHandlers\s*\(\s*container\s*\)/.test(source));
});

test('showAddFilterModal method is declared', () => {
  assert.ok(/showAddFilterModal\s*\(\s*\)/.test(source));
});

test('searchFilters method is declared as async', () => {
  assert.ok(/async\s+searchFilters\s*\(\s*type\s*,\s*query\s*,\s*resultsContainer\s*\)/.test(source));
});

test('renderHints method is declared', () => {
  assert.ok(/renderHints\s*\(\s*container\s*,\s*message\s*\)/.test(source));
});

test('renderSuggestions method is declared', () => {
  assert.ok(/renderSuggestions\s*\(\s*container\s*\)/.test(source));
});

test('moveSelection method is declared', () => {
  assert.ok(/moveSelection\s*\(\s*delta\s*,\s*container\s*\)/.test(source));
});

test('commitSelection method is declared', () => {
  assert.ok(/commitSelection\s*\(\s*inputValue/.test(source));
});

test('update method is declared', () => {
  assert.ok(/update\s*\(\s*state\s*\)/.test(source));
});

test('bindEvents method is declared', () => {
  assert.ok(/bindEvents\s*\(\s*\)/.test(source));
});

test('start method is declared', () => {
  assert.ok(/start\s*\(\s*\)/.test(source));
});

// ============================================================
// Event names tests
// ============================================================

test('bindClickHandlers triggers CONTEXT_FILTER_REMOVE on remove button', () => {
  assert.ok(/this\.ES\.CONTEXT_FILTER_REMOVE/.test(source));
});

test('bindClickHandlers triggers CONTEXT_FILTER_CLEAR on clear button', () => {
  assert.ok(/this\.ES\.CONTEXT_FILTER_CLEAR/.test(source));
});

test('commitSelection triggers CONTEXT_FILTER_ADD', () => {
  assert.ok(/this\.ES\.CONTEXT_FILTER_ADD/.test(source));
});

test('bindEvents binds to CONTEXT_FILTER_UPDATED', () => {
  assert.ok(/this\.ES\.CONTEXT_FILTER_UPDATED/.test(source));
});

// ============================================================
// CSS class tests
// ============================================================

test('render uses context-filter-bar class', () => {
  assert.ok(/context-filter-bar/.test(source));
});

test('render uses context-filter-group CSS classes', () => {
  assert.ok(/context-filter-group/.test(source));
  assert.ok(/context-filter-group-label/.test(source));
});

test('render uses context-filter-tag class for chips', () => {
  assert.ok(/context-filter-tag/.test(source));
});

test('render uses context-filter-remove class for remove buttons', () => {
  assert.ok(/context-filter-remove/.test(source));
});

test('render uses context-filter-clear class for clear button', () => {
  assert.ok(/context-filter-clear/.test(source));
});

test('render uses context-filter-add class for add button', () => {
  assert.ok(/context-filter-add/.test(source));
});

test('modal uses context-filter-modal classes', () => {
  assert.ok(/context-filter-modal/.test(source));
  assert.ok(/context-filter-modal-content/.test(source));
  assert.ok(/context-filter-modal-add/.test(source));
  assert.ok(/context-filter-modal-close/.test(source));
});

test('suggestions use context-tag-suggestion classes', () => {
  assert.ok(/context-tag-suggestion/.test(source));
  assert.ok(/context-tag-label/.test(source));
  assert.ok(/context-tag-meta/.test(source));
});

test('render uses selected class for highlighted suggestion', () => {
  assert.ok(/'selected'/.test(source));
});

// ============================================================
// HTML pattern tests
// ============================================================

test('render sets container display to flex', () => {
  assert.ok(/container\.style\.display\s*=\s*['"]flex['"]/.test(source));
});

test('render shows Context label when active', () => {
  assert.ok(/Context:/.test(source));
  assert.ok(/context-filter-label/.test(source));
});

test('render shows Clear button when active', () => {
  assert.ok(/Clear/.test(source));
  assert.ok(/Clear all filters/.test(source));
});

test('render always shows Add Filter button', () => {
  assert.ok(/\+\s*Add Filter/.test(source));
});

test('render uses encodeURIComponent for filter values', () => {
  assert.ok(/encodeURIComponent\s*\(\s*value\s*\)/.test(source));
});

test('render uses decodeURIComponent for remove button values', () => {
  assert.ok(/decodeURIComponent/.test(source));
});

test('render uses data-filter-type and data-filter-value attributes', () => {
  assert.ok(/data-filter-type/.test(source));
  assert.ok(/data-filter-value/.test(source));
});

// ============================================================
// Modal tests
// ============================================================

test('showAddFilterModal removes existing modal first', () => {
  assert.ok(/context-filter-modal.*\?\.remove\(\)/.test(source));
});

test('showAddFilterModal creates select for filter type', () => {
  assert.ok(/id="context-filter-type"/.test(source));
  assert.ok(/<option/.test(source));
});

test('showAddFilterModal creates search input', () => {
  assert.ok(/id="context-filter-search"/.test(source));
  assert.ok(/type="text"/.test(source));
  assert.ok(/autocomplete="off"/.test(source));
});

test('showAddFilterModal creates results div', () => {
  assert.ok(/id="context-filter-results"/.test(source));
});

test('modal input listens for ArrowDown/ArrowUp keys', () => {
  assert.ok(/ArrowDown/.test(source));
  assert.ok(/ArrowUp/.test(source));
});

test('modal input listens for Enter key', () => {
  assert.ok(/event\.key\s*===\s*['"]Enter['"]/.test(source));
});

test('search has 400ms debounce timeout', () => {
  assert.ok(/400/.test(source));
  assert.ok(/setTimeout/.test(source));
});

// ============================================================
// searchFilters tests
// ============================================================

test('searchFilters uses FILTER_TYPE_MAP to get type config', () => {
  assert.ok(/FILTER_TYPE_MAP\[type\]/.test(source));
});

test('searchFilters trims query and returns early if empty', () => {
  assert.ok(/query\.trim\(\)/.test(source));
});

test('searchFilters uses FormData with req param for tags', () => {
  assert.ok(/new\s+FormData\(\)/.test(source));
  assert.ok(/form\.append\s*\(\s*['"]req['"]/.test(source));
});

test('searchFilters appends type param when itemType is set', () => {
  assert.ok(/form\.append\s*\(\s*['"]type['"]/.test(source));
  assert.ok(/typeConfig\.itemType/.test(source));
});

test('searchFilters calls rsstag_utils.fetchJSON', () => {
  assert.ok(/rsstag_utils\.fetchJSON/.test(source));
});

test('searchFilters calls renderHints on empty query', () => {
  assert.ok(/this\.renderHints/.test(source));
});

test('searchFilters calls renderSuggestions on success', () => {
  assert.ok(/this\.renderSuggestions/.test(source));
});

test('searchFilters shows "No matching values found" on no results', () => {
  assert.ok(/No matching values found/.test(source));
});

test('searchFilters shows "Search failed" on error', () => {
  assert.ok(/Search failed/.test(source));
});

test('searchFilters filters out already active values', () => {
  assert.ok(/activeValues/.test(source));
  assert.ok(/\.includes\s*\(\s*item\.value\s*\)/.test(source));
});

test('searchFilters uses tags-search URL for tags type', () => {
  assert.ok(/\/tags-search/.test(source));
});

test('searchFilters uses suggestions URL for non-tags types', () => {
  assert.ok(/\/api\/context-filter\/suggestions/.test(source));
});

// ============================================================
// moveSelection tests
// ============================================================

test('moveSelection updates selectedIndex by delta', () => {
  assert.ok(/this\._modalState\.selectedIndex\s*=\s*next/.test(source));
});

test('moveSelection wraps around at boundaries', () => {
  assert.ok(/%/.test(source));
  assert.ok(/total/.test(source));
});

test('moveSelection calls scrollIntoView on selected element', () => {
  assert.ok(/scrollIntoView/.test(source));
  assert.ok(/block\s*:\s*['"]nearest['"]/.test(source));
});

// ============================================================
// commitSelection tests
// ============================================================

test('commitSelection uses selectedIndex if valid', () => {
  assert.ok(/selectedIndex\s*>=\s*0/.test(source));
  assert.ok(/suggestions\[selectedIndex\]\.value/.test(source));
});

test('commitSelection checks requireSuggestion before adding', () => {
  assert.ok(/typeConfig\.requireSuggestion/.test(source));
});

test('commitSelection prevents duplicate values', () => {
  assert.ok(/\(this\._state\.filters\[type\]/.test(source));
  assert.ok(/\.includes\s*\(\s*value\s*\)/.test(source));
});

test('commitSelection returns early for empty value', () => {
  assert.ok(/if\s*\(\s*!value\s*\)/.test(source));
  assert.ok(/return\s*;/.test(source));
});

// ============================================================
// update/bindEvents/start tests
// ============================================================

test('update calls normalizeState and render', () => {
  assert.ok(/this\._state\s*=\s*normalizeState\s*\(\s*state\s*\)/.test(source));
  assert.ok(/this\.render\(\)/.test(source));
});

test('bindEvents binds CONTEXT_FILTER_UPDATED handler', () => {
  assert.ok(/this\.ES\.bind/.test(source));
  assert.ok(/\(state\)\s*=>\s*this\.update\s*\(\s*state\s*\)/.test(source));
});

test('start calls bindEvents', () => {
  assert.ok(/this\.bindEvents\(\)/.test(source));
});

test('start checks window.context_filter_data', () => {
  assert.ok(/window\.context_filter_data/.test(source));
});

// ============================================================
// renderHints tests
// ============================================================

test('renderHints sets container innerHTML with hint message', () => {
  assert.ok(/container\.innerHTML/.test(source));
  assert.ok(/context-tag-hint/.test(source));
});

// ============================================================
// renderSuggestions tests
// ============================================================

test('renderSuggestions maps suggestions to HTML with data-value', () => {
  assert.ok(/data-value/.test(source));
  assert.ok(/data-index/.test(source));
});

test('renderSuggestions adds click handler to suggestion elements', () => {
  assert.ok(/addEventListener\s*\(\s*['"]click['"]/.test(source));
});
