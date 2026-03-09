import test from 'node:test';
import assert from 'node:assert/strict';

import GeoTagsStorage from '../storages/geo-tags-storage.js';
import { createEventSystem } from './helpers.js';

function createGeoEventSystem() {
  return Object.assign(createEventSystem(), {
    MAP_UPDATED: 'map_updated',
    CHANGE_MAP_OBJECTS_VISIBILITY: 'change_map_objects_visibility',
  });
}

test('constructor default state snapshot follows current getState implementation', () => {
  const storage = new GeoTagsStorage(createGeoEventSystem());

  assert.deepEqual(storage.getState(), {});
});

test('start() binds CHANGE_MAP_OBJECTS_VISIBILITY', () => {
  global.window = {
    initial_countries_list: [],
    initial_cities_list: [],
  };
  const es = createGeoEventSystem();
  const storage = new GeoTagsStorage(es);

  storage.start();

  assert.equal(es.bindings.has(es.CHANGE_MAP_OBJECTS_VISIBILITY), true);
});

test('changeVisibilityState() success path updates state and emits payload shape', () => {
  const es = createGeoEventSystem();
  const storage = new GeoTagsStorage(es);

  storage.setState({
    countries: new Map(),
    cities: new Map(),
    show_countries: false,
    show_cities: false,
  });
  es.calls.length = 0;

  storage.changeVisibilityState({ show_cities: true, show_countries: false });

  assert.deepEqual(es.calls.at(-1), {
    event: es.MAP_UPDATED,
    payload: {
      countries: new Map(),
      cities: new Map(),
      show_countries: false,
      show_cities: true,
    },
  });
});

test('changeVisibilityState() failure/invalid payload path emits no update', () => {
  const es = createGeoEventSystem();
  const storage = new GeoTagsStorage(es);

  storage.setState({
    countries: new Map(),
    cities: new Map(),
    show_countries: false,
    show_cities: false,
  });
  es.calls.length = 0;

  storage.changeVisibilityState(null);

  assert.equal(es.calls.length, 0);
});
