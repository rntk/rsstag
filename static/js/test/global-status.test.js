import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'global-status.js');

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

test('class name is GlobalStatus', () => {
  const src = readSource();
  assert.ok(/export default class GlobalStatus/.test(src),
    'should define class GlobalStatus');
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

test('constructor initializes state with msgs, is_ok, promptType, promptValue', () => {
  const src = readSource();
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?msgs\s*:/.test(src),
    'should set state.msgs');
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?is_ok\s*:/.test(src),
    'should set state.is_ok');
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?promptType\s*:/.test(src),
    'should set state.promptType');
  assert.ok(/this\.state\s*=\s*\{[\s\S]*?promptValue\s*:/.test(src),
    'should set state.promptValue');
});

test('constructor stores ES reference from props', () => {
  const src = readSource();
  assert.ok(/this\.ES\s*=\s*props\.ES/.test(src),
    'should store this.ES = props.ES');
});

test('constructor initializes timeout_handler to 0', () => {
  const src = readSource();
  assert.ok(/this\.timeout_handler\s*=\s*0/.test(src),
    'should initialize timeout_handler = 0');
});

test('constructor creates promptInputRef with React.createRef', () => {
  const src = readSource();
  assert.ok(/this\.promptInputRef\s*=\s*React\.createRef/.test(src),
    'should create promptInputRef via React.createRef');
});

test('constructor binds immediatlyCheck method', () => {
  const src = readSource();
  assert.ok(/this\.immediatlyCheck\s*=\s*this\.checkStatusAfter\.bind/.test(src),
    'should bind immediatlyCheck to checkStatusAfter');
});

// ============================================================
// Method declaration tests
// ============================================================

test('source declares checkStatusAfter method', () => {
  const src = readSource();
  assert.ok(/checkStatusAfter\s*\(/.test(src),
    'should declare checkStatusAfter() method');
});

test('checkStatusAfter uses setTimeout for scheduling', () => {
  const src = readSource();
  assert.ok(/setTimeout/.test(src),
    'should use setTimeout');
});

test('checkStatusAfter clears previous timeout', () => {
  const src = readSource();
  assert.ok(/clearTimeout/.test(src),
    'should call clearTimeout before setting new timeout');
});

test('checkStatusAfter calls fetchStatus', () => {
  const src = readSource();
  assert.ok(/this\.fetchStatus/.test(src),
    'should call fetchStatus in timeout callback');
});

test('source declares fetchStatus method', () => {
  const src = readSource();
  assert.ok(/fetchStatus\s*\(\s*\)/.test(src),
    'should declare fetchStatus() method');
});

test('fetchStatus calls /status endpoint', () => {
  const src = readSource();
  assert.ok(/['"]\/status['"]/.test(src),
    'should fetch from /status endpoint');
});

test('fetchStatus uses GET method', () => {
  const src = readSource();
  assert.ok(/method\s*:\s*['"]GET['"]/.test(src),
    'should use GET method');
});

test('fetchStatus sets credentials include', () => {
  const src = readSource();
  assert.ok(/credentials\s*:\s*['"]include['"]/.test(src),
    'should include credentials');
});

test('fetchStatus sets Content-Type header', () => {
  const src = readSource();
  assert.ok(/Content-Type/.test(src),
    'should set Content-Type header');
});

test('fetchStatus calls checkStatusAfter with 60000ms interval', () => {
  const src = readSource();
  assert.ok(/60000/.test(src),
    'should schedule next check after 60 seconds');
});

test('source declares openTelegramPrompt method', () => {
  const src = readSource();
  assert.ok(/openTelegramPrompt\s*\(/.test(src),
    'should declare openTelegramPrompt() method');
});

test('source declares handlePromptChange method', () => {
  const src = readSource();
  assert.ok(/handlePromptChange\s*=/.test(src),
    'should declare handlePromptChange arrow function');
});

test('source declares handlePromptSubmit method', () => {
  const src = readSource();
  assert.ok(/handlePromptSubmit\s*=/.test(src),
    'should declare handlePromptSubmit arrow function');
});

test('handlePromptSubmit calls preventDefault', () => {
  const src = readSource();
  assert.ok(/preventDefault/.test(src),
    'should call preventDefault on event');
});

test('handlePromptSubmit triggers SAVE_TELEGRAM_PASSWORD', () => {
  const src = readSource();
  assert.ok(/SAVE_TELEGRAM_PASSWORD/.test(src),
    'should trigger SAVE_TELEGRAM_PASSWORD event');
});

test('handlePromptSubmit triggers SAVE_TELEGRAM_CODE', () => {
  const src = readSource();
  assert.ok(/SAVE_TELEGRAM_CODE/.test(src),
    'should trigger SAVE_TELEGRAM_CODE event');
});

// ============================================================
// Lifecycle method tests
// ============================================================

test('source declares componentDidMount lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidMount\s*\(\s*\)/.test(src),
    'should declare componentDidMount() method');
});

test('componentDidMount schedules initial status check', () => {
  const src = readSource();
  assert.ok(/componentDidMount[\s\S]*?checkStatusAfter/.test(src),
    'should call checkStatusAfter in componentDidMount');
});

test('source declares componentDidUpdate lifecycle method', () => {
  const src = readSource();
  assert.ok(/componentDidUpdate\s*\(/.test(src),
    'should declare componentDidUpdate() method');
});

test('componentDidUpdate focuses input on promptType change', () => {
  const src = readSource();
  assert.ok(/\.focus\s*\(\s*\)/.test(src),
    'should call .focus() on input');
  assert.ok(/promptInputRef\.current/.test(src),
    'should use promptInputRef.current for focus');
});

// ============================================================
// Render structure tests
// ============================================================

test('source declares render method', () => {
  const src = readSource();
  assert.ok(/render\s*\(\s*\)\s*\{/.test(src),
    'should declare render() method');
});

test('render returns null when state is null', () => {
  const src = readSource();
  assert.ok(/if\s*\(\s*!\s*this\.state\s*\)\s*\{[\s\S]*?return null/.test(src),
    'should return null when state is falsy');
});

test('render uses React.Fragment', () => {
  const src = readSource();
  assert.ok(/React\.Fragment/.test(src),
    'should use React.Fragment wrapper');
});

test('render shows error link with error CSS class', () => {
  const src = readSource();
  assert.ok(/className.*['"]error['"]/.test(src),
    'should use error CSS class on error link');
});

test('render error link points to /provider', () => {
  const src = readSource();
  assert.ok(/['"]\/provider['"]/.test(src),
    'should link to /provider on error');
});

test('render uses abbr element for status display', () => {
  const src = readSource();
  assert.ok(/<abbr/.test(src),
    'should use <abbr> element for status');
});

test('render shows ERROR in title attribute', () => {
  const src = readSource();
  assert.ok(/ERROR/.test(src),
    'should include ERROR in title');
});

test('render shows Working in title attribute', () => {
  const src = readSource();
  assert.ok(/Working/.test(src),
    'should include Working in title for active tasks');
});

test('render shows No active tasks in title', () => {
  const src = readSource();
  assert.ok(/No active tasks/.test(src),
    'should include "No active tasks" in title');
});

test('render uses refresh unicode character', () => {
  const src = readSource();
  assert.ok(/&#x27F3;/.test(src) || /&#x21bb;/.test(src),
    'should use refresh symbol (U+27F3 or U+21BB)');
});

test('render calls immediatlyCheck on status click', () => {
  const src = readSource();
  assert.ok(/onClick\s*=\s*\{?\s*this\.immediatlyCheck/.test(src),
    'should bind immediatlyCheck to onClick');
});

// ============================================================
// Telegram auth modal tests
// ============================================================

test('render includes telegram-auth-overlay CSS class', () => {
  const src = readSource();
  assert.ok(/telegram-auth-overlay/.test(src),
    'should use telegram-auth-overlay CSS class');
});

test('render includes telegram-auth-modal CSS class', () => {
  const src = readSource();
  assert.ok(/telegram-auth-modal/.test(src),
    'should use telegram-auth-modal CSS class');
});

test('render includes telegram-auth-label CSS class', () => {
  const src = readSource();
  assert.ok(/telegram-auth-label/.test(src),
    'should use telegram-auth-label CSS class');
});

test('render includes telegram-auth-input CSS class', () => {
  const src = readSource();
  assert.ok(/telegram-auth-input/.test(src),
    'should use telegram-auth-input CSS class');
});

test('render includes telegram-auth-submit CSS class', () => {
  const src = readSource();
  assert.ok(/telegram-auth-submit/.test(src),
    'should use telegram-auth-submit CSS class');
});

test('modal form has onSubmit handler', () => {
  const src = readSource();
  assert.ok(/onSubmit\s*=\s*\{?\s*this\.handlePromptSubmit/.test(src),
    'should bind handlePromptSubmit to form onSubmit');
});

test('input uses onChange to handlePromptChange', () => {
  const src = readSource();
  assert.ok(/onChange\s*=\s*\{?\s*this\.handlePromptChange/.test(src),
    'should bind handlePromptChange to input onChange');
});

test('input has required attribute', () => {
  const src = readSource();
  assert.ok(/required/.test(src),
    'should have required on input');
});

test('modal uses password input type for sensitive prompts', () => {
  const src = readSource();
  assert.ok(/password/.test(src),
    'should use type="password" for telegram prompts');
});

test('modal uses autoComplete for one-time-code or current-password', () => {
  const src = readSource();
  assert.ok(/current-password/.test(src),
    'should use current-password autoComplete');
  assert.ok(/one-time-code/.test(src),
    'should use one-time-code autoComplete');
});

test('modal shows Telegram password label', () => {
  const src = readSource();
  assert.ok(/Telegram password/.test(src),
    'should include "Telegram password" label');
});

test('modal shows Telegram code label', () => {
  const src = readSource();
  assert.ok(/Telegram code/.test(src),
    'should include "Telegram code" label');
});

test('modal renders conditionally based on promptType', () => {
  const src = readSource();
  assert.ok(/this\.state\.promptType &&/.test(src),
    'should conditionally render modal based on promptType');
});

// ============================================================
// State handling tests
// ============================================================

test('fetchStatus checks data.data.is_ok', () => {
  const src = readSource();
  assert.ok(/data\.data\.is_ok/.test(src),
    'should check data.data.is_ok');
});

test('fetchStatus checks data.data.msgs', () => {
  const src = readSource();
  assert.ok(/data\.data\.msgs/.test(src),
    'should check data.data.msgs');
});

test('fetchStatus checks telegram_password flag', () => {
  const src = readSource();
  assert.ok(/telegram_password/.test(src),
    'should check telegram_password flag');
});

test('fetchStatus checks telegram_code flag', () => {
  const src = readSource();
  assert.ok(/telegram_code/.test(src),
    'should check telegram_code flag');
});

// ============================================================
// Import and dependency tests
// ============================================================

test('source imports React', () => {
  const src = readSource();
  assert.ok(/import React from/.test(src),
    'should import React');
});

test('source imports rsstag_utils', () => {
  const src = readSource();
  assert.ok(/import.*rsstag_utils/.test(src),
    'should import rsstag_utils');
});

test('source uses rsstag_utils.fetchJSON', () => {
  const src = readSource();
  assert.ok(/rsstag_utils\s*\.\s*fetchJSON/.test(src),
    'should use rsstag_utils.fetchJSON');
});
