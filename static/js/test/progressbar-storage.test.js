import test from 'node:test';
import assert from 'node:assert/strict';

import ProgressBarStorage from '../storages/progressbar-storage.js';
import rsstag_utils from '../libs/rsstag_utils.js';
import { createEventSystem } from './helpers.js';

function createProgressEventSystem() {
  return Object.assign(createEventSystem(), {
    CHANGE_PROGRESSBAR: 'change_progressbar',
    START_TASK: 'start_task',
    END_TASK: 'end_task',
    PROGRESSBAR_ANIMATION_END: 'progressbar_animation_end',
  });
}

test('constructor sets default state snapshot', () => {
  const storage = new ProgressBarStorage(createProgressEventSystem());

  assert.deepEqual(storage.getState(), { tasks: [], progress: 0 });
});

test('start() binds task and animation events', () => {
  const es = createProgressEventSystem();
  const storage = new ProgressBarStorage(es);

  storage.start();

  assert.equal(es.bindings.has(es.START_TASK), true);
  assert.equal(es.bindings.has(es.END_TASK), true);
  assert.equal(es.bindings.has(es.PROGRESSBAR_ANIMATION_END), true);
});

test('startTask/endTask success path emits CHANGE_PROGRESSBAR payload shape', (t) => {
  const es = createProgressEventSystem();
  const storage = new ProgressBarStorage(es);
  const originalRandInt = rsstag_utils.randInt;
  rsstag_utils.randInt = () => 42;
  t.after(() => {
    rsstag_utils.randInt = originalRandInt;
  });

  storage.startTask('ajax');
  storage.endTask();

  const lastCall = es.calls.at(-1);
  assert.equal(lastCall.event, es.CHANGE_PROGRESSBAR);
  assert.deepEqual(lastCall.payload, { tasks: [], progress: 100 });
});

test('endTask() with no active tasks is handled as edge failure path', () => {
  const es = createProgressEventSystem();
  const storage = new ProgressBarStorage(es);

  storage.endTask();

  assert.deepEqual(storage.getState(), { tasks: [], progress: 100 });
  assert.equal(es.calls.at(-1).event, es.CHANGE_PROGRESSBAR);
});
