import test from 'node:test';
import assert from 'node:assert/strict';
import { label, timeAgo, sortQueue, nextStatus } from './format.js';

test('label turns enum values into words', () => {
  assert.equal(label('IN_PROGRESS'), 'In Progress');
  assert.equal(label('URGENT'), 'Urgent');
});

test('timeAgo buckets durations', () => {
  const now = Date.parse('2026-10-07T12:00:00Z');
  assert.equal(timeAgo('2026-10-07T11:59:30Z', now), '30s ago');
  assert.equal(timeAgo('2026-10-07T11:00:00Z', now), '1h ago');
  assert.equal(timeAgo('2026-10-05T12:00:00Z', now), '2d ago');
});

test('sortQueue puts urgent and older tickets first', () => {
  const sorted = sortQueue([
    { id: 1, priority: 'LOW', created_at: '2026-01-01' },
    { id: 2, priority: 'URGENT', created_at: '2026-01-03' },
    { id: 3, priority: 'URGENT', created_at: '2026-01-02' },
  ]);
  assert.deepEqual(sorted.map((t) => t.id), [3, 2, 1]);
});

test('nextStatus walks the workflow and stops at CLOSED', () => {
  assert.equal(nextStatus('OPEN'), 'IN_PROGRESS');
  assert.equal(nextStatus('RESOLVED'), 'CLOSED');
  assert.equal(nextStatus('CLOSED'), null);
});
