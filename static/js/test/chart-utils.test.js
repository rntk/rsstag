import test from 'node:test';
import assert from 'node:assert/strict';

import { calculateBins, smoothBins, estimateCharacterCounts } from '../libs/chart-utils.js';

test('calculateBins creates correct number of bins', () => {
  const topics = [
    { name: 'A', sentences: [0, 1, 2, 5, 6] },
    { name: 'B', sentences: [3, 4, 7, 8, 9] },
  ];

  const bins = calculateBins(5, topics, 0, 10);

  assert.equal(bins.length, 5);
  assert.equal(bins[0].x, 0);
  assert.equal(bins[4].x, 4);
});

test('calculateBins correctly counts sentences per bin', () => {
  const topics = [
    { name: 'A', sentences: [0, 1, 2] },
    { name: 'B', sentences: [5, 6, 7] },
  ];

  const bins = calculateBins(5, topics, 0, 10);

  // Bin 0 covers [0, 2): sentences 0, 1 -> A=2
  assert.equal(bins[0].A, 2);
  assert.equal(bins[0].B, 0);

  // Bin 2 covers [4, 6): sentence 5 -> B=1
  assert.equal(bins[2].A, 0);
  assert.equal(bins[2].B, 1);

  // Bin 3 covers [6, 8): sentences 6, 7 -> B=2
  assert.equal(bins[3].B, 2);
});

test('calculateBins handles empty topics', () => {
  const bins = calculateBins(3, [], 0, 9);

  assert.equal(bins.length, 3);
  assert.equal(bins[0].rangeStart, 0);
  assert.equal(bins[0].rangeEnd, 3);
  assert.equal(bins[1].rangeStart, 3);
  assert.equal(bins[1].rangeEnd, 6);
});

test('calculateBins binSize is at least 1 when range is small', () => {
  const topics = [{ name: 'X', sentences: [0] }];
  const bins = calculateBins(10, topics, 0, 5);

  assert.equal(bins.length, 10);
});

test('smoothBins interpolates zeros between non-zero values', () => {
  const topics = [{ name: 'A' }];
  const bins = [
    { x: 0, A: 10 },
    { x: 1, A: 0 },
    { x: 2, A: 10 },
  ];

  const smoothed = smoothBins(bins, topics);

  // Middle bin has prev=10 and next=10, so min(10,10)*0.3 = 3
  assert.equal(smoothed[1].A, 3);
});

test('smoothBins handles zero at the edge', () => {
  const topics = [{ name: 'A' }];
  const bins = [
    { x: 0, A: 0 },
    { x: 1, A: 10 },
    { x: 2, A: 20 },
  ];

  const smoothed = smoothBins(bins, topics);

  // First bin: prev=0, next=10 -> max(0,10)*0.1 = 1
  assert.equal(smoothed[0].A, 1);
});

test('smoothBins smooths non-zero values with weighted average', () => {
  const topics = [{ name: 'A' }];
  const bins = [
    { x: 0, A: 10 },
    { x: 1, A: 20 },
    { x: 2, A: 30 },
  ];

  const smoothed = smoothBins(bins, topics);

  // Middle bin: 20*0.6 + 10*0.2 + 30*0.2 = 12 + 2 + 6 = 20
  assert.equal(smoothed[1].A, 20);
});

test('smoothBins preserves structure with multiple topics', () => {
  const topics = [{ name: 'A' }, { name: 'B' }];
  const bins = [
    { x: 0, A: 5, B: 3 },
    { x: 1, A: 0, B: 0 },
    { x: 2, A: 5, B: 3 },
  ];

  const smoothed = smoothBins(bins, topics);

  assert.ok(smoothed[1].A > 0);
  assert.ok(smoothed[1].B > 0);
});

test('estimateCharacterCounts multiplies sentence counts by avgCharsPerSentence', () => {
  const topics = [
    { name: 'A', avgCharsPerSentence: 100 },
    { name: 'B', avgCharsPerSentence: 50 },
  ];
  const bins = [{ x: 0, A: 3, B: 2 }];

  const result = estimateCharacterCounts(bins, topics);

  assert.equal(result.length, 1);
  assert.equal(result[0].A, 300);
  assert.equal(result[0].B, 100);
});

test('estimateCharacterCounts uses default 100 chars when avgCharsPerSentence is missing', () => {
  const topics = [{ name: 'X' }];
  const bins = [{ x: 0, X: 5 }];

  const result = estimateCharacterCounts(bins, topics);

  assert.equal(result[0].X, 500);
});

test('estimateCharacterCounts handles zero sentence counts', () => {
  const topics = [{ name: 'A', avgCharsPerSentence: 80 }];
  const bins = [{ x: 0, A: 0 }];

  const result = estimateCharacterCounts(bins, topics);

  assert.equal(result[0].A, 0);
});

test('smoothBins with all zeros produces all zeros', () => {
  const topics = [{ name: 'A' }];
  const bins = [
    { x: 0, A: 0 },
    { x: 1, A: 0 },
    { x: 2, A: 0 },
  ];

  const smoothed = smoothBins(bins, topics);

  assert.equal(smoothed[0].A, 0);
  assert.equal(smoothed[1].A, 0);
  assert.equal(smoothed[2].A, 0);
});

test('smoothBins handles single bin', () => {
  const topics = [{ name: 'A' }];
  const bins = [{ x: 0, A: 10 }];

  const smoothed = smoothBins(bins, topics);

  assert.equal(smoothed[0].A, 10);
});

test('smoothBins uses current value as prev/next for single non-zero bin at edge', () => {
  const topics = [{ name: 'A' }];
  const bins = [
    { x: 0, A: 10 },
    { x: 1, A: 0 },
  ];

  const smoothed = smoothBins(bins, topics);

  // Bin 1: prev=10, next=0 -> max(10,0)*0.1 = 1
  assert.equal(smoothed[1].A, 1);
});

test('smoothBins non-zero at end uses current value as next', () => {
  const topics = [{ name: 'A' }];
  const bins = [
    { x: 0, A: 0 },
    { x: 1, A: 10 },
  ];

  const smoothed = smoothBins(bins, topics);

  // Bin 0: prev=0, next=10 -> max(0,10)*0.1 = 1
  assert.equal(smoothed[0].A, 1);
});

test('estimateCharacterCounts with empty bins returns empty array', () => {
  const result = estimateCharacterCounts([], []);
  assert.deepEqual(result, []);
});

test('estimateCharacterCounts with empty topics preserves bin structure', () => {
  const bins = [{ x: 0, A: 5 }];
  const result = estimateCharacterCounts(bins, []);
  assert.deepEqual(result, [{ x: 0, A: 5 }]);
});
