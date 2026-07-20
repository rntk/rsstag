import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT_PATH = path.join(__dirname, '..', 'components', 'rsstag-ymaps.js');

function readSource() {
  return fs.readFileSync(COMPONENT_PATH, 'utf8');
}

// ============================================================
// Class and constructor tests
// ============================================================

test('source exports a default class', () => {
  const src = readSource();
  assert.ok(
    /export default class RssTagYMap/.test(src),
    'should export a default class RssTagYMap'
  );
});

test('class does not extend React.Component (vanilla JS)', () => {
  const src = readSource();
  assert.ok(!/extends React/.test(src), 'should not extend React.Component');
});

test('constructor accepts map_id and ES parameters', () => {
  const src = readSource();
  assert.ok(
    /constructor\s*\(\s*map_id\s*,\s*ES\s*\)/.test(src),
    'should have constructor(map_id, ES)'
  );
});

test('constructor initializes y_map to null', () => {
  const src = readSource();
  assert.ok(/this\.y_map\s*=\s*null/.test(src), 'should initialize y_map to null');
});

test('constructor assigns map_id', () => {
  const src = readSource();
  assert.ok(/this\.map_id\s*=\s*map_id/.test(src), 'should assign map_id');
});

test('constructor assigns ES', () => {
  const src = readSource();
  assert.ok(/this\.ES\s*=\s*ES/.test(src), 'should assign ES');
});

test('constructor initializes geo_cities to null', () => {
  const src = readSource();
  assert.ok(/this\.geo_cities\s*=\s*null/.test(src), 'should initialize geo_cities to null');
});

test('constructor initializes geo_countries to null', () => {
  const src = readSource();
  assert.ok(/this\.geo_countries\s*=\s*null/.test(src), 'should initialize geo_countries to null');
});

test('constructor initializes state to empty object', () => {
  const src = readSource();
  assert.ok(/this\.state\s*=\s*\{\}/.test(src), 'should initialize state to empty object');
});

test('source has no import statements (pure vanilla JS)', () => {
  const src = readSource();
  assert.ok(!/^import /m.test(src), 'should have no imports');
});

// ============================================================
// updateMap method tests
// ============================================================

test('source declares updateMap method', () => {
  const src = readSource();
  assert.ok(/updateMap\s*\(\s*state\s*\)\s*\{/.test(src), 'should declare updateMap(state) method');
});

test('updateMap calls processCitiesState', () => {
  const src = readSource();
  assert.ok(
    /this\.processCitiesState\s*\(\s*state\s*\)/.test(src),
    'should call processCitiesState(state)'
  );
});

test('updateMap calls processCountriesState', () => {
  const src = readSource();
  assert.ok(
    /this\.processCountriesState\s*\(\s*state\s*\)/.test(src),
    'should call processCountriesState(state)'
  );
});

// ============================================================
// processCitiesState method tests
// ============================================================

test('source declares processCitiesState method', () => {
  const src = readSource();
  assert.ok(
    /processCitiesState\s*\(\s*state\s*\)\s*\{/.test(src),
    'should declare processCitiesState(state) method'
  );
});

test('processCitiesState checks state.show_cities', () => {
  const src = readSource();
  assert.ok(/state\.show_cities/.test(src), 'should check state.show_cities');
});

test('processCitiesState creates GeoObjectCollection when cities shown', () => {
  const src = readSource();
  assert.ok(
    /new ymaps\.GeoObjectCollection\s*\(\s*\)/.test(src),
    'should create new ymaps.GeoObjectCollection'
  );
});

test('processCitiesState checks geo_cities is null or empty', () => {
  const src = readSource();
  assert.ok(/this\.geo_cities\s*===\s*null/.test(src), 'should check if geo_cities is null');
  assert.ok(
    /this\.geo_cities\.getLength\s*\(\s*\)\s*===\s*0/.test(src),
    'should check geo_cities.getLength()'
  );
});

test('processCitiesState iterates over state.cities', () => {
  const src = readSource();
  assert.ok(/for\s*\(\s*let tag of state\.cities/.test(src), 'should iterate over state.cities');
});

test('processCitiesState creates Placemark with coordinates', () => {
  const src = readSource();
  assert.ok(/new ymaps\.Placemark/.test(src), 'should create ymaps.Placemark');
  assert.ok(/tag\[1\]\.city\.co\[1\]/.test(src), 'should use tag[1].city.co[1] for latitude');
  assert.ok(/tag\[1\]\.city\.co\[0\]/.test(src), 'should use tag[1].city.co[0] for longitude');
});

test('processCitiesState sets hintContent with tag info', () => {
  const src = readSource();
  assert.ok(/hintContent/.test(src), 'should set hintContent');
  assert.ok(/tag\[1\]\.tag/.test(src), 'should include tag name');
  assert.ok(/tag\[1\]\.unread_count/.test(src), 'should include unread_count');
  assert.ok(/tag\[1\]\.posts_count/.test(src), 'should include posts_count');
});

test('processCitiesState sets balloonContentHeader', () => {
  const src = readSource();
  assert.ok(/balloonContentHeader/.test(src), 'should set balloonContentHeader');
});

test('processCitiesState sets balloonContentBody with links', () => {
  const src = readSource();
  assert.ok(/balloonContentBody/.test(src), 'should set balloonContentBody');
  assert.ok(/\/tag-info\/\$\{tag\[1\]\.tag\}/.test(src), 'should include tag info link');
  assert.ok(/\$\{tag\[1\]\.local_url\}/.test(src), 'should include posts link');
});

test('processCitiesState adds collection to map geoObjects', () => {
  const src = readSource();
  assert.ok(
    /this\.y_map\.geoObjects\.add\s*\(\s*this\.geo_cities\s*\)/.test(src),
    'should add geo_cities to map'
  );
});

test('processCitiesState removes all when cities not shown', () => {
  const src = readSource();
  assert.ok(
    /this\.geo_cities\.removeAll\s*\(\s*\)/.test(src),
    'should call geo_cities.removeAll()'
  );
});

test('processCitiesState null-checks geo_cities before removeAll', () => {
  const src = readSource();
  assert.ok(
    /if\s*\(\s*this\.geo_cities\s*!==\s*null\s*\)/.test(src),
    'should check geo_cities !== null before removeAll'
  );
});

// ============================================================
// processCountriesState method tests
// ============================================================

test('source declares processCountriesState method', () => {
  const src = readSource();
  assert.ok(
    /processCountriesState\s*\(\s*state\s*\)\s*\{/.test(src),
    'should declare processCountriesState(state) method'
  );
});

test('processCountriesState checks state.show_countries', () => {
  const src = readSource();
  assert.ok(/state\.show_countries/.test(src), 'should check state.show_countries');
});

test('processCountriesState creates GeoObjectCollection when countries shown', () => {
  const src = readSource();
  assert.ok(
    /new ymaps\.GeoObjectCollection\s*\(\s*\)/.test(src),
    'should create new ymaps.GeoObjectCollection'
  );
});

test('processCountriesState checks geo_countries is null or empty', () => {
  const src = readSource();
  assert.ok(/this\.geo_countries\s*===\s*null/.test(src), 'should check if geo_countries is null');
  assert.ok(
    /this\.geo_countries\.getLength\s*\(\s*\)/.test(src),
    'should check geo_countries.getLength()'
  );
});

test('processCountriesState iterates over state.countries', () => {
  const src = readSource();
  assert.ok(
    /for\s*\(\s*let tag of state\.countries/.test(src),
    'should iterate over state.countries'
  );
});

test('processCountriesState creates Placemark with country coordinates', () => {
  const src = readSource();
  assert.ok(/new ymaps\.Placemark/.test(src), 'should create ymaps.Placemark');
  assert.ok(/tag\[1\]\.country\.co/.test(src), 'should use tag[1].country.co for coordinates');
});

test('processCountriesState sets hintContent with country info', () => {
  const src = readSource();
  assert.ok(/hintContent/.test(src), 'should set hintContent');
  assert.ok(/tag\[1\]\.tag/.test(src), 'should include tag name');
});

test('processCountriesState sets balloonContentBody with links', () => {
  const src = readSource();
  assert.ok(/balloonContentBody/.test(src), 'should set balloonContentBody');
  assert.ok(/\/tag-info\/\$\{tag\[1\]\.tag\}/.test(src), 'should include tag info link');
});

test('processCountriesState adds collection to map geoObjects', () => {
  const src = readSource();
  assert.ok(
    /this\.y_map\.geoObjects\.add\s*\(\s*this\.geo_countries\s*\)/.test(src),
    'should add geo_countries to map'
  );
});

test('processCountriesState removes all when countries not shown', () => {
  const src = readSource();
  assert.ok(
    /this\.geo_countries\.removeAll\s*\(\s*\)/.test(src),
    'should call geo_countries.removeAll()'
  );
});

// ============================================================
// bindEvents method tests
// ============================================================

test('source declares bindEvents method', () => {
  const src = readSource();
  assert.ok(/bindEvents\s*\(\s*\)\s*\{/.test(src), 'should declare bindEvents() method');
});

test('bindEvents binds MAP_UPDATED event', () => {
  const src = readSource();
  assert.ok(
    /this\.ES\.bind\s*\(\s*this\.ES\.MAP_UPDATED/.test(src),
    'should bind MAP_UPDATED event'
  );
  assert.ok(/this\.updateMap\.bind\s*\(\s*this\s*\)/.test(src), 'should bind updateMap to this');
});

// ============================================================
// isReadyToStart method tests
// ============================================================

test('source declares isReadyToStart method', () => {
  const src = readSource();
  assert.ok(/isReadyToStart\s*\(\s*\)\s*\{/.test(src), 'should declare isReadyToStart() method');
});

test('isReadyToStart checks ymaps exists', () => {
  const src = readSource();
  assert.ok(/return ymaps && ymaps\.Map/.test(src), 'should return ymaps && ymaps.Map');
});

// ============================================================
// start method tests
// ============================================================

test('source declares start method', () => {
  const src = readSource();
  assert.ok(/start\s*\(\s*\)\s*\{/.test(src), 'should declare start() method');
});

test('start creates ymaps.Map with this.map_id', () => {
  const src = readSource();
  assert.ok(
    /new window\.ymaps\.Map\s*\(\s*this\.map_id/.test(src),
    'should create new window.ymaps.Map with map_id'
  );
});

test('start sets default center coordinates', () => {
  const src = readSource();
  assert.ok(
    /center\s*:\s*\[46\.91252944\s*,\s*7\.98097972\]/.test(src),
    'should set center to [46.91252944, 7.98097972]'
  );
});

test('start sets default zoom level', () => {
  const src = readSource();
  assert.ok(/zoom\s*:\s*2/.test(src), 'should set zoom to 2');
});

test('start calls bindEvents after creating map', () => {
  const src = readSource();
  assert.ok(/this\.bindEvents\s*\(\s*\)/.test(src), 'should call bindEvents()');
});
