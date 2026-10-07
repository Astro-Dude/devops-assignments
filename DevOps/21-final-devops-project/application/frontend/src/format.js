// Pure helpers, unit-tested with `node --test` (no browser needed).

export const STATUSES = ['OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'];
export const PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'];
export const CATEGORIES = ['GENERAL', 'ACCESS', 'HARDWARE', 'NETWORK', 'BILLING'];

export function label(value) {
  return value
    .toLowerCase()
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export function timeAgo(iso, now = Date.now()) {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

// Order the queue the way an agent works it: urgent first, then oldest first.
export function sortQueue(tickets) {
  const weight = { URGENT: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
  return [...tickets].sort(
    (a, b) => weight[a.priority] - weight[b.priority] || new Date(a.created_at) - new Date(b.created_at),
  );
}

export function nextStatus(status) {
  const i = STATUSES.indexOf(status);
  return i >= 0 && i < STATUSES.length - 1 ? STATUSES[i + 1] : null;
}
