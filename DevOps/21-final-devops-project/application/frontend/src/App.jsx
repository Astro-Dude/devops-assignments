import { useCallback, useEffect, useState } from 'react';
import { api } from './api.js';
import { CATEGORIES, PRIORITIES, STATUSES, label, nextStatus, sortQueue, timeAgo } from './format.js';

const EMPTY_FORM = { subject: '', requester: '', description: '', category: 'GENERAL', priority: 'MEDIUM' };

function Kpi({ title, value, tone }) {
  return (
    <div className={`kpi kpi-${tone}`}>
      <span className="kpi-title">{title}</span>
      <span className="kpi-value">{value ?? '–'}</span>
    </div>
  );
}

function Badge({ kind, value }) {
  return <span className={`badge ${kind}-${value.toLowerCase()}`}>{label(value)}</span>;
}

function NewTicketModal({ onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    try {
      await api.create(form);
      onCreated();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>Raise a ticket</h2>
        <label>Subject<input value={form.subject} onChange={set('subject')} required minLength={3} /></label>
        <label>Requester email<input value={form.requester} onChange={set('requester')} required /></label>
        <label>Description<textarea rows={3} value={form.description} onChange={set('description')} /></label>
        <div className="row">
          <label>Category
            <select value={form.category} onChange={set('category')}>
              {CATEGORIES.map((c) => <option key={c} value={c}>{label(c)}</option>)}
            </select>
          </label>
          <label>Priority
            <select value={form.priority} onChange={set('priority')}>
              {PRIORITIES.map((p) => <option key={p} value={p}>{label(p)}</option>)}
            </select>
          </label>
        </div>
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="button" className="ghost" onClick={onClose}>Cancel</button>
          <button type="submit">Create ticket</button>
        </div>
      </form>
    </div>
  );
}

function TicketDetail({ ticket, onChanged }) {
  const [comments, setComments] = useState([]);
  const [body, setBody] = useState('');

  useEffect(() => {
    api.comments(ticket.id).then(setComments).catch(() => setComments([]));
  }, [ticket.id]);

  async function advance() {
    await api.update(ticket.id, { status: nextStatus(ticket.status) });
    onChanged();
  }
  async function remove() {
    await api.remove(ticket.id);
    onChanged(true);
  }
  async function comment(e) {
    e.preventDefault();
    if (!body.trim()) return;
    await api.addComment(ticket.id, { author: 'agent', body });
    setBody('');
    setComments(await api.comments(ticket.id));
  }

  return (
    <aside className="detail">
      <div className="detail-head">
        <span className="ticket-id">#{ticket.id}</span>
        <Badge kind="status" value={ticket.status} />
      </div>
      <h3>{ticket.subject}</h3>
      <p className="muted">{ticket.requester} · {label(ticket.category)} · {ticket.team}</p>
      {ticket.description && <p>{ticket.description}</p>}
      <div className="actions">
        {nextStatus(ticket.status) && (
          <button onClick={advance}>Move to {label(nextStatus(ticket.status))}</button>
        )}
        <button className="danger" onClick={remove}>Delete</button>
      </div>
      <h4>Conversation ({comments.length})</h4>
      <ul className="comments">
        {comments.map((c) => (
          <li key={c.id}><strong>{c.author}</strong> <span className="muted">{timeAgo(c.created_at)}</span><p>{c.body}</p></li>
        ))}
      </ul>
      <form onSubmit={comment} className="comment-form">
        <input placeholder="Add an internal note…" value={body} onChange={(e) => setBody(e.target.value)} />
        <button type="submit">Post</button>
      </form>
    </aside>
  );
}

export default function App() {
  const [info, setInfo] = useState(null);
  const [stats, setStats] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [filter, setFilter] = useState('');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async (deselect = false) => {
    try {
      const [s, t] = await Promise.all([api.stats(), api.tickets({ status: filter, q: query })]);
      setStats(s);
      setTickets(sortQueue(t));
      setError('');
      if (deselect) setSelected(null);
      else setSelected((cur) => (cur ? t.find((x) => x.id === cur.id) ?? null : null));
    } catch (err) {
      setError(`Backend unreachable — ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [filter, query]);

  useEffect(() => { api.info().then(setInfo).catch(() => {}); }, []);
  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="brand">Ticket<span>Hub</span></div>
        <p className="sidebar-caption">IT Helpdesk</p>
        <button className={!filter ? 'nav active' : 'nav'} onClick={() => setFilter('')}>All tickets</button>
        {STATUSES.map((s) => (
          <button key={s} className={filter === s ? 'nav active' : 'nav'} onClick={() => setFilter(s)}>{label(s)}</button>
        ))}
        <div className="build">
          <div>env: <b>{info?.environment ?? '…'}</b></div>
          <div>version: <b>{info?.version ?? '…'}</b></div>
          <div>pod: <b>{info?.pod ?? '…'}</b></div>
        </div>
      </nav>

      <main>
        <header className="topbar">
          <div>
            <h1>Support queue</h1>
            <p className="muted">Urgent first, then oldest first · default team: {info?.default_team ?? '…'}</p>
          </div>
          <div className="top-actions">
            <input className="search" placeholder="Search subject…" value={query} onChange={(e) => setQuery(e.target.value)} />
            <button onClick={() => setShowNew(true)}>+ New ticket</button>
          </div>
        </header>

        <section className="kpis">
          <Kpi title="Open" value={stats?.open} tone="blue" />
          <Kpi title="In progress" value={stats?.in_progress} tone="amber" />
          <Kpi title="Resolved" value={stats?.resolved} tone="green" />
          <Kpi title="Urgent backlog" value={stats?.urgent_open} tone="red" />
        </section>

        {error && <div className="banner">{error}</div>}

        <section className="content">
          <div className="table-wrap">
            {loading ? <p className="muted pad">Loading tickets…</p> : tickets.length === 0 ? (
              <p className="muted pad">No tickets here. Raise one with “New ticket”.</p>
            ) : (
              <table>
                <thead><tr><th>#</th><th>Subject</th><th>Requester</th><th>Priority</th><th>Status</th><th>Age</th></tr></thead>
                <tbody>
                  {tickets.map((t) => (
                    <tr key={t.id} className={selected?.id === t.id ? 'selected' : ''} onClick={() => setSelected(t)}>
                      <td className="ticket-id">{t.id}</td>
                      <td>{t.subject}<div className="muted small">{label(t.category)}</div></td>
                      <td>{t.requester}</td>
                      <td><Badge kind="priority" value={t.priority} /></td>
                      <td><Badge kind="status" value={t.status} /></td>
                      <td className="muted">{timeAgo(t.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {selected && <TicketDetail key={selected.id + selected.status} ticket={selected} onChanged={refresh} />}
        </section>
      </main>

      {showNew && <NewTicketModal onClose={() => setShowNew(false)} onCreated={() => { setShowNew(false); refresh(); }} />}
    </div>
  );
}
