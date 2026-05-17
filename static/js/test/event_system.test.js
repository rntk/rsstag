import test from 'node:test';
import assert from 'node:assert/strict';

import EventsSystem from '../libs/event_system.js';

test('constructor initializes all event constants and empty state', () => {
  const es = new EventsSystem();

  assert.equal(es.POSTS_UPDATED, 'posts_updated');
  assert.equal(es.START_TASK, 'start_task');
  assert.equal(es.END_TASK, 'end_task');
  assert.deepEqual(es._events, {});
  assert.deepEqual(es._last_events, {});
});

test('bind registers a handler and trigger calls it with args', () => {
  const es = new EventsSystem();
  const results = [];

  es.bind('test_event', (a, b) => {
    results.push([a, b]);
  });

  es.trigger('test_event', 'hello', 42);

  assert.deepEqual(results, [['hello', 42]]);
});

test('trigger with no registered handlers is a no-op', () => {
  const es = new EventsSystem();

  es.trigger('nonexistent_event', 'payload');

  assert.deepEqual(es._last_events['nonexistent_event'], ['payload']);
});

test('unbind removes a specific handler', () => {
  const es = new EventsSystem();
  const results = [];

  const handler1 = () => results.push(1);
  const handler2 = () => results.push(2);

  es.bind('evt', handler1);
  es.bind('evt', handler2);

  es.unbind('evt', handler1);
  es.trigger('evt');

  assert.deepEqual(results, [2]);
});

test('unbind for unregistered event does not throw', () => {
  const es = new EventsSystem();

  const handler = () => {};
  es.unbind('never_bound', handler);
});

test('bind replays last_events when binding after a trigger', () => {
  const es = new EventsSystem();
  const results = [];

  es.trigger('late_event', 'replayed');

  es.bind('late_event', (val) => {
    results.push(val);
  });

  assert.deepEqual(results, ['replayed']);
});

test('trigger updates _last_events for replay on future binds', () => {
  const es = new EventsSystem();

  es.trigger('my_event', 'first');
  assert.deepEqual(es._last_events['my_event'], ['first']);

  es.trigger('my_event', 'second', 'extra');
  assert.deepEqual(es._last_events['my_event'], ['second', 'extra']);
});

test('multiple handlers fire in registration order', () => {
  const es = new EventsSystem();
  const order = [];

  es.bind('multi', () => order.push('a'));
  es.bind('multi', () => order.push('b'));
  es.bind('multi', () => order.push('c'));

  es.trigger('multi');

  assert.deepEqual(order, ['a', 'b', 'c']);
});
