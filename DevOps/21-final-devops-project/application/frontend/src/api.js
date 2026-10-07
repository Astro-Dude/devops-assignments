// The browser only ever talks to relative /api/... URLs.
// docker compose: nginx proxies /api to the backend container.
// Kubernetes:     the Ingress routes /api to the backend Service.
async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text.slice(0, 120)}`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  info: () => request('/api/info'),
  stats: () => request('/api/stats'),
  tickets: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
    return request(`/api/tickets${qs ? `?${qs}` : ''}`);
  },
  create: (body) => request('/api/tickets', { method: 'POST', body: JSON.stringify(body) }),
  update: (id, body) => request(`/api/tickets/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  remove: (id) => request(`/api/tickets/${id}`, { method: 'DELETE' }),
  comments: (id) => request(`/api/tickets/${id}/comments`),
  addComment: (id, body) =>
    request(`/api/tickets/${id}/comments`, { method: 'POST', body: JSON.stringify(body) }),
};
