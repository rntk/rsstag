import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'settings-menu.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class extending React.Component', () => {
  const src = readSource();
  assert.ok(/export default class \w+ extends React\.Component/.test(src),
    'should export a default class extending React.Component');
});

test('class name is SettingsMenu', () => {
  const src = readSource();
  assert.ok(/export default class SettingsMenu/.test(src),
    'should define class SettingsMenu');
});

test('constructor accepts props parameter', () => {
  const src = readSource();
  assert.ok(/constructor\s*\(\s*props\s*\)/.test(src),
    'should have constructor(props)');
});

test('constructor calls super(props)', () => {
  const src = readSource();
  assert.ok(/super\s*\(\s*props\s*\)/.test(src),
    'should call super(props)');
});

// ============================================================
// Method binding tests
// ============================================================

test('constructor binds saveSettings method', () => {
  const src = readSource();
  assert.ok(/this\.saveSettings\s*=\s*this\.saveSettings\.bind\(this\)/.test(src),
    'should bind saveSettings');
});

test('constructor binds updateSettings method', () => {
  const src = readSource();
  assert.ok(/this\.updateSettings\s*=\s*this\.updateSettings\.bind\(this\)/.test(src),
    'should bind updateSettings');
});

test('constructor binds changeIntSettings method', () => {
  const src = readSource();
  assert.ok(/this\.changeIntSettings\s*=\s*this\.changeIntSettings\.bind\(this\)/.test(src),
    'should bind changeIntSettings');
});

test('constructor binds changeBoolSettings method', () => {
  const src = readSource();
  assert.ok(/this\.changeBoolSettings\s*=\s*this\.changeBoolSettings\.bind\(this\)/.test(src),
    'should bind changeBoolSettings');
});

test('constructor binds changeStringSettings method', () => {
  const src = readSource();
  assert.ok(/this\.changeStringSettings\s*=\s*this\.changeStringSettings\.bind\(this\)/.test(src),
    'should bind changeStringSettings');
});

test('constructor binds hideMenu method', () => {
  const src = readSource();
  assert.ok(/this\.hideMenu\s*=\s*this\.hideMenu\.bind\(this\)/.test(src),
    'should bind hideMenu');
});

test('constructor binds handleKeyDown method', () => {
  const src = readSource();
  assert.ok(/this\.handleKeyDown\s*=\s*this\.handleKeyDown\.bind\(this\)/.test(src),
    'should bind handleKeyDown');
});

test('constructor binds handleClickOutside method', () => {
  const src = readSource();
  assert.ok(/this\.handleClickOutside\s*=\s*this\.handleClickOutside\.bind\(this\)/.test(src),
    'should bind handleClickOutside');
});

test('constructor creates menuRef with React.createRef', () => {
  const src = readSource();
  assert.ok(/this\.menuRef\s*=\s*React\.createRef/.test(src),
    'should create menuRef via React.createRef');
});

// ============================================================
// Settings method tests
// ============================================================

test('source declares saveSettings method', () => {
  const src = readSource();
  assert.ok(/saveSettings\s*\(\s*\)/.test(src),
    'should declare saveSettings() method');
});

test('saveSettings triggers UPDATE_SETTINGS event', () => {
  const src = readSource();
  assert.ok(/UPDATE_SETTINGS/.test(src),
    'should reference UPDATE_SETTINGS');
  assert.ok(/this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.UPDATE_SETTINGS/.test(src),
    'should trigger UPDATE_SETTINGS via ES');
});

test('saveSettings sends a copy of settings', () => {
  const src = readSource();
  assert.ok(/Object\.assign\s*\(\s*\{\s*\}/.test(src),
    'should use Object.assign({}, ...) for copy');
  assert.ok(/this\.state\.settings/.test(src),
    'should copy state.settings');
});

test('source declares hideMenu method', () => {
  const src = readSource();
  assert.ok(/hideMenu\s*\(\s*\)/.test(src),
    'should declare hideMenu() method');
});

test('hideMenu triggers CHANGE_SETTINGS_WINDOW_STATE event', () => {
  const src = readSource();
  assert.ok(/CHANGE_SETTINGS_WINDOW_STATE/.test(src),
    'should reference CHANGE_SETTINGS_WINDOW_STATE');
  assert.ok(/this\.props\.ES\.trigger\s*\(\s*this\.props\.ES\.CHANGE_SETTINGS_WINDOW_STATE/.test(src),
    'should trigger CHANGE_SETTINGS_WINDOW_STATE');
});

test('source declares updateSettings method', () => {
  const src = readSource();
  assert.ok(/updateSettings\s*\(/.test(src),
    'should declare updateSettings() method');
});

test('updateSettings calls setState with state parameter', () => {
  const src = readSource();
  assert.ok(/this\.setState\s*\(\s*state\s*\)/.test(src),
    'should call setState(state)');
});

// ============================================================
// Input handler method tests
// ============================================================

test('source declares changeIntSettings method', () => {
  const src = readSource();
  assert.ok(/changeIntSettings\s*\(/.test(src),
    'should declare changeIntSettings() method');
});

test('changeIntSettings uses parseInt', () => {
  const src = readSource();
  assert.ok(/parseInt/.test(src),
    'should use parseInt');
});

test('changeIntSettings reads e.target.value', () => {
  const src = readSource();
  assert.ok(/e\.target\.value/.test(src),
    'should read e.target.value');
});

test('changeIntSettings reads e.target.id', () => {
  const src = readSource();
  assert.ok(/e\.target\.id/.test(src),
    'should read e.target.id');
});

test('changeIntSettings checks isNaN', () => {
  const src = readSource();
  assert.ok(/isNaN/.test(src),
    'should check isNaN');
});

test('changeIntSettings returns true on success', () => {
  const src = readSource();
  assert.ok(/return true/.test(src),
    'should return true');
});

test('changeIntSettings returns false on failure', () => {
  const src = readSource();
  assert.ok(/return false/.test(src),
    'should return false');
});

test('source declares changeStringSettings method', () => {
  const src = readSource();
  assert.ok(/changeStringSettings\s*\(/.test(src),
    'should declare changeStringSettings() method');
});

test('source declares changeBoolSettings method', () => {
  const src = readSource();
  assert.ok(/changeBoolSettings\s*\(/.test(src),
    'should declare changeBoolSettings() method');
});

test('changeBoolSettings reads e.target.checked', () => {
  const src = readSource();
  assert.ok(/e\.target\.checked/.test(src),
    'should read e.target.checked');
});

// ============================================================
// Event handler tests
// ============================================================

test('source declares handleKeyDown method', () => {
  const src = readSource();
  assert.ok(/handleKeyDown\s*\(/.test(src),
    'should declare handleKeyDown() method');
});

test('handleKeyDown checks for Escape key', () => {
  const src = readSource();
  assert.ok(/e\.key\s*===\s*['"]Escape['"]/.test(src),
    'should check e.key === "Escape"');
});

test('handleKeyDown calls hideMenu on Escape', () => {
  const src = readSource();
  assert.ok(/this\.hideMenu/.test(src),
    'should call hideMenu');
});

test('source declares handleClickOutside method', () => {
  const src = readSource();
  assert.ok(/handleClickOutside\s*\(/.test(src),
    'should declare handleClickOutside() method');
});

test('handleClickOutside checks menuRef.current', () => {
  const src = readSource();
  assert.ok(/this\.menuRef\.current/.test(src),
    'should check menuRef.current');
});

test('handleClickOutside uses contains method', () => {
  const src = readSource();
  assert.ok(/\.contains\s*\(\s*e\.target/.test(src),
    'should call contains(e.target)');
});

test('handleClickOutside calls hideMenu when clicking outside', () => {
  const src = readSource();
  assert.ok(/this\.hideMenu/.test(src),
    'should call hideMenu');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)/.test(src),
    'should declare componentDidMount() method');
});

test('componentDidMount binds SETTINGS_UPDATED event', () => {
  const src = readSource();
  assert.ok(/SETTINGS_UPDATED/.test(src),
    'should reference SETTINGS_UPDATED');
  assert.ok(/this\.props\.ES\.bind\s*\(\s*this\.props\.ES\.SETTINGS_UPDATED/.test(src),
    'should bind SETTINGS_UPDATED event');
});

test('source declares componentDidUpdate lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidUpdate\s*\(/.test(src),
    'should declare componentDidUpdate() method');
});

test('componentDidUpdate adds event listeners when menu is shown', () => {
  const src = readSource();
  assert.ok(/document\.addEventListener\s*\(\s*['"]keydown['"]/.test(src),
    'should add keydown listener');
  assert.ok(/document\.addEventListener\s*\(\s*['"]mousedown['"]/.test(src),
    'should add mousedown listener');
});

test('componentDidUpdate removes event listeners when menu is hidden', () => {
  const src = readSource();
  assert.ok(/document\.removeEventListener\s*\(\s*['"]keydown['"]/.test(src),
    'should remove keydown listener');
  assert.ok(/document\.removeEventListener\s*\(\s*['"]mousedown['"]/.test(src),
    'should remove mousedown listener');
});

test('componentDidUpdate checks showed transition from false to true', () => {
  const src = readSource();
  assert.ok(/prevState/.test(src),
    'should reference prevState');
  assert.ok(/\.showed/.test(src),
    'should check showed property');
});

test('source declares componentWillUnmount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentWillUnmount\s*\(\s*\)/.test(src),
    'should declare componentWillUnmount() method');
});

test('componentWillUnmount unbinds SETTINGS_UPDATED', () => {
  const src = readSource();
  assert.ok(/this\.props\.ES\.unbind\s*\(\s*this\.props\.ES\.SETTINGS_UPDATED/.test(src),
    'should unbind SETTINGS_UPDATED');
});

test('componentWillUnmount removes document event listeners', () => {
  const src = readSource();
  assert.ok(/removeEventListener/.test(src),
    'should remove event listeners');
  assert.ok(/keydown/.test(src) && /mousedown/.test(src),
    'should remove both keydown and mousedown listeners');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render uses SettingsMenuButton component', () => {
  const src = readSource();
  assert.ok(/SettingsMenuButton/.test(src),
    'should render SettingsMenuButton');
});

test('render passes ES prop to SettingsMenuButton', () => {
  const src = readSource();
  assert.ok(/ES\s*=\s*\{?\s*this\.props\.ES/.test(src),
    'should pass ES prop to button');
});

test('render passes src prop with menu.png', () => {
  const src = readSource();
  assert.ok(/src\s*=\s*['"]\/static\/img\/menu\.png['"]/.test(src),
    'should pass src="/static/img/menu.png"');
});

test('render returns button only when menu is hidden', () => {
  const src = readSource();
  assert.ok(/this\.state && this\.state\.showed\s*===\s*true/.test(src),
    'should check showed === true');
});

test('render menu uses main_menu_window CSS class', () => {
  const src = readSource();
  assert.ok(/main_menu_window/.test(src),
    'should use main_menu_window CSS class');
});

// ============================================================
// Menu input field tests
// ============================================================

test('render includes posts_on_page input', () => {
  const src = readSource();
  assert.ok(/posts_on_page/.test(src),
    'should include posts_on_page setting');
  assert.ok(/id\s*=\s*['"]posts_on_page['"]/.test(src),
    'should have id="posts_on_page"');
  assert.ok(/posts per page/.test(src),
    'should include "posts per page" label');
});

test('render includes tags_on_page input', () => {
  const src = readSource();
  assert.ok(/tags_on_page/.test(src),
    'should include tags_on_page setting');
  assert.ok(/id\s*=\s*['"]tags_on_page['"]/.test(src),
    'should have id="tags_on_page"');
  assert.ok(/tags per page/.test(src),
    'should include "tags per page" label');
});

test('render includes context_n input', () => {
  const src = readSource();
  assert.ok(/context_n/.test(src),
    'should include context_n setting');
  assert.ok(/id\s*=\s*['"]context_n['"]/.test(src),
    'should have id="context_n"');
  assert.ok(/context size/.test(src),
    'should include "context size" label');
});

test('render includes telegram_limit input', () => {
  const src = readSource();
  assert.ok(/telegram_limit/.test(src),
    'should include telegram_limit setting');
  assert.ok(/telegram limit/.test(src),
    'should include telegram limit label');
});

// ============================================================
// LLM provider select tests
// ============================================================

test('render includes batch_llm select', () => {
  const src = readSource();
  assert.ok(/batch_llm/.test(src),
    'should include batch_llm setting');
  assert.ok(/Batch LLM/.test(src),
    'should include "Batch LLM" label');
  assert.ok(/<select/.test(src),
    'should include select elements');
});

test('render includes worker_llm select', () => {
  const src = readSource();
  assert.ok(/worker_llm/.test(src),
    'should include worker_llm setting');
  assert.ok(/Worker LLM/.test(src),
    'should include "Worker LLM" label');
});

test('render includes realtime_llm select', () => {
  const src = readSource();
  assert.ok(/realtime_llm/.test(src),
    'should include realtime_llm setting');
  assert.ok(/Realtime LLM/.test(src),
    'should include "Realtime LLM" label');
});

test('render includes llamacpp option', () => {
  const src = readSource();
  assert.ok(/llamacpp/.test(src),
    'should include llamacpp option');
});

test('render includes openai option', () => {
  const src = readSource();
  assert.ok(/openai/.test(src),
    'should include openai option');
});

test('render includes anthropic option', () => {
  const src = readSource();
  assert.ok(/anthropic/.test(src),
    'should include anthropic option');
});

test('render includes cerebras option', () => {
  const src = readSource();
  assert.ok(/cerebras/.test(src),
    'should include cerebras option');
});

test('render includes groqcom option', () => {
  const src = readSource();
  assert.ok(/groqcom/.test(src),
    'should include groqcom option');
});

test('render includes nebius option in batch LLM', () => {
  const src = readSource();
  assert.ok(/nebius/.test(src),
    'should include nebius option');
});

test('batch_llm has more options than worker/realtime (includes nebius)', () => {
  const src = readSource();
  assert.ok(/batchLlmOptions/.test(src),
    'should define batchLlmOptions variable');
  assert.ok(/llmOptions/.test(src),
    'should define llmOptions variable');
  assert.ok(/\.\.\.llmOptions/.test(src),
    'should spread llmOptions into batchLlmOptions');
});

// ============================================================
// Boolean toggle tests
// ============================================================

test('render includes only_unread checkbox', () => {
  const src = readSource();
  assert.ok(/only_unread/.test(src),
    'should include only_unread checkbox');
  assert.ok(/only unread/.test(src),
    'should include "only unread" label');
});

test('render includes hot_tags checkbox', () => {
  const src = readSource();
  assert.ok(/hot_tags/.test(src),
    'should include hot_tags checkbox');
  assert.ok(/hot tags/.test(src),
    'should include "hot tags" label');
});

test('render includes similar_posts checkbox', () => {
  const src = readSource();
  assert.ok(/similar_posts/.test(src),
    'should include similar_posts checkbox');
  assert.ok(/similar posts/.test(src),
    'should include "similar posts" label');
});

// ============================================================
// Save button tests
// ============================================================

test('render includes save button with id="save_settings"', () => {
  const src = readSource();
  assert.ok(/id\s*=\s*['"]save_settings['"]/.test(src),
    'should have id="save_settings"');
  assert.ok(/Save/.test(src),
    'should include "Save" text');
});

test('save button has onClick handler', () => {
  const src = readSource();
  assert.ok(/onClick\s*=\s*\{?\s*this\.saveSettings/.test(src),
    'should bind onClick to saveSettings');
});

// ============================================================
// Style and ref tests
// ============================================================

test('menu window uses style with top and right', () => {
  const src = readSource();
  assert.ok(/style\s*=\s*\{?\s*style/.test(src),
    'should use style prop');
  assert.ok(/this\.state\.offset\.top/.test(src),
    'should use offset.top');
  assert.ok(/this\.state\.offset\.right/.test(src),
    'should use offset.right');
});

test('menu window uses ref with menuRef', () => {
  const src = readSource();
  assert.ok(/ref\s*=\s*\{?\s*this\.menuRef/.test(src),
    'should use menuRef as ref');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src),
    'should import React');
});

test('source imports SettingsMenuButton', () => {
  const src = readSource();
  assert.ok(/import SettingsMenuButton from/.test(src),
    'should import SettingsMenuButton');
});
