import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'tag-tool-widget.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class TagToolWidget extending React.Component', () => {
  const src = readSource();
  assert.ok(/export default class TagToolWidget extends React\.Component/.test(src),
    'should export TagToolWidget extending React.Component');
});

test('constructor initializes state with hidden true, loading false, tags null, error null', () => {
  const src = readSource();
  assert.ok(/this\.state\s*=\s*\{\s*hidden:\s*true,\s*loading:\s*false,\s*tags:\s*null,\s*error:\s*null\s*\}/.test(src),
    'should set initial state');
});

test('constructor binds loadData', () => {
  const src = readSource();
  assert.ok(/this\.loadData\s*=\s*this\.loadData\.bind\(this\)/.test(src),
    'should bind loadData');
});

// ============================================================
// Import tests
// ============================================================

test('source imports createPortal from react-dom', () => {
  const src = readSource();
  assert.ok(/import\s*\{\s*createPortal\s*\}\s*from\s*['"]react-dom['"]/.test(src),
    'should import createPortal from react-dom');
});

test('source imports TagsList', () => {
  const src = readSource();
  assert.ok(/import TagsList from ['"]\.\/tags-list\.js['"]/.test(src),
    'should import TagsList');
});

test('source imports rsstag_utils', () => {
  const src = readSource();
  assert.ok(/import rsstag_utils from ['"]..\/libs\/rsstag_utils\.js['"]/.test(src),
    'should import rsstag_utils');
});

// ============================================================
// loadData: hide branch (state.hidden === false)
// ============================================================

test('loadData hides and clears tags when already shown', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*!this\.state\.hidden\s*\)\s*\{[\s\S]*?this\.setState\(\{\s*hidden:\s*true,\s*tags:\s*null\s*\}\)/.test(src),
    'should reset hidden and tags on hide click');
});

test('loadData clears renderData container on hide', () => {
  const src = readSource();
  assert.ok(/clearRenderData/.test(src),
    'should call clearRenderData');
  assert.ok(/container\.innerHTML\s*=\s*['"]{2}/.test(src),
    'should clear container innerHTML');
});

// ============================================================
// loadData: fetch branch
// ============================================================

test('loadData fetches url with encodeURIComponent(tag) via rsstag_utils.fetchJSON', () => {
  const src = readSource();
  assert.ok(/rsstag_utils\s*\.\s*fetchJSON\s*\(\s*this\.props\.url\s*\+\s*['"]\/['"]\s*\+\s*encodeURIComponent\(this\.props\.tag\)/.test(src),
    'should build the fetch url from props.url and encoded props.tag');
});

test('fetchJSON is called with GET, credentials include and JSON content-type', () => {
  const src = readSource();
  assert.ok(/method:\s*['"]GET['"]/.test(src));
  assert.ok(/credentials:\s*['"]include['"]/.test(src));
  assert.ok(/['"]Content-Type['"]\s*:\s*['"]application\/json['"]/.test(src));
});

test('on success with data.data, tags are normalized and hidden is set false', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*data\.data\s*\)\s*\{[\s\S]*?normalizedTags\(data\.data\)[\s\S]*?hidden:\s*false/.test(src),
    'should normalize tags and set hidden false on success');
});

test('on missing data.data, an inline error is set', () => {
  const src = readSource();
  assert.ok(/error:\s*['"]Error\. Try later['"]/.test(src),
    'should set the inline error message');
});

test('on fetch rejection, error is logged and inline error is set', () => {
  const src = readSource();
  assert.ok(/\.catch\s*\(\s*\(err\)\s*=>\s*\{[\s\S]*?console\.log\(err\)[\s\S]*?error:\s*['"]Error\. Try later['"]/.test(src),
    'should log and set error on catch');
});

// ============================================================
// normalizedTags helper
// ============================================================

test('normalizedTags sorts by count descending with localeCompare tie-break', () => {
  const src = readSource();
  assert.ok(/const countDiff\s*=\s*\(b\.count \|\| 0\)\s*-\s*\(a\.count \|\| 0\)/.test(src),
    'should compute descending count diff');
  assert.ok(/localeCompare\(bt,\s*undefined,\s*\{\s*numeric:\s*true,\s*sensitivity:\s*['"]base['"]\s*\}\)/.test(src),
    'should tie-break with localeCompare numeric/base');
});

test('normalizedTags sets root:true on each tag and keys the Map by tag.tag', () => {
  const src = readSource();
  assert.ok(/tag\.root\s*=\s*true/.test(src),
    'should set root: true on each tag');
  assert.ok(/tags\.set\(tag\.tag,\s*tag\)/.test(src),
    'should key the Map by tag.tag');
});

// ============================================================
// render tests
// ============================================================

test('render toggles button label between Load <title> and Hide <title>', () => {
  const src = readSource();
  assert.ok(/const prefix\s*=\s*this\.state\.hidden\s*\?\s*['"]Load\s*['"]\s*:\s*['"]Hide\s*['"]/.test(src),
    'should compute Load/Hide prefix from state.hidden');
  assert.ok(/\{prefix\s*\+\s*this\.props\.title\}/.test(src),
    'should render prefix + title');
});

test('render shows the inline error text when present', () => {
  const src = readSource();
  assert.ok(/this\.state\.error\s*\?\s*<span>\{this\.state\.error\}<\/span>/.test(src),
    'should render the error inline');
});

test('render portals TagsList into the list container when not hidden and renderData is absent', () => {
  const src = readSource();
  assert.ok(/createPortal\(\s*<TagsList/.test(src),
    'should createPortal a TagsList');
  assert.ok(/!this\.state\.hidden\s*&&\s*container/.test(src),
    'should only portal when visible and container exists');
});

test('render passes tags, is_bigram and is_entities props to the portaled TagsList', () => {
  const src = readSource();
  assert.ok(/tags=\{this\.state\.tags\}/.test(src));
  assert.ok(/is_bigram=\{this\.props\.is_bigram\}/.test(src));
  assert.ok(/is_entities=\{this\.props\.is_entities\}/.test(src));
});

test('render resolves the portal container via document.getElementById(props.listContainerId), skipped when renderData is set', () => {
  const src = readSource();
  assert.ok(/!this\.props\.renderData\s*&&\s*document\.getElementById\(this\.props\.listContainerId\)/.test(src),
    'should look up the container only in non-renderData mode');
});

// ============================================================
// renderData imperative mode
// ============================================================

test('loadData calls renderData(container, tags) imperatively on success when provided', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*this\.props\.renderData\s*\)\s*\{[\s\S]*?this\.props\.renderData\(container,\s*tags\)/.test(src),
    'should call renderData with the container and tags map');
});

test('componentWillUnmount clears the renderData container', () => {
  const src = readSource();
  assert.ok(/componentWillUnmount\s*\(\s*\)\s*\{[\s\S]*?clearRenderData\(\)/.test(src),
    'should call clearRenderData on unmount');
});
