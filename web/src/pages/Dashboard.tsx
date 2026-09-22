import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { LogOut, Plus, RefreshCcw } from "lucide-react";
import { api, type Ticket } from "../api/client";
import type { Session } from "../App";
import { StatusPill } from "../components/StatusPill";

type Props = {
  session: Session;
  onLogout: () => void;
};

export default function Dashboard({ session, onLogout }: Props) {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const openCount = useMemo(
    () => tickets.filter((ticket) => ticket.status === "open" || ticket.status === "triaged").length,
    [tickets],
  );

  const loadTickets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setTickets(await api.listTickets(session.access_token));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load tickets");
    } finally {
      setLoading(false);
    }
  }, [session.access_token]);

  async function createTicket(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      return;
    }
    setError(null);
    try {
      const ticket = await api.createTicket(session.access_token, title.trim());
      setTickets((current) => [ticket, ...current]);
      setTitle("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create ticket");
    }
  }

  useEffect(() => {
    void loadTickets();
  }, [loadTickets]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">SupportPilot</p>
          <h1>Tickets</h1>
        </div>
        <div className="topbar-actions">
          <span className="user-chip">{session.email}</span>
          <button className="icon-button" onClick={loadTickets} title="Refresh tickets" type="button">
            <RefreshCcw size={18} aria-hidden="true" />
          </button>
          <button className="icon-button" onClick={onLogout} title="Sign out" type="button">
            <LogOut size={18} aria-hidden="true" />
          </button>
        </div>
      </header>

      <section className="summary-grid">
        <div>
          <span>Total</span>
          <strong>{tickets.length}</strong>
        </div>
        <div>
          <span>Needs attention</span>
          <strong>{openCount}</strong>
        </div>
        <div>
          <span>Resolved</span>
          <strong>{tickets.filter((ticket) => ticket.status === "resolved").length}</strong>
        </div>
      </section>

      <form className="create-row" onSubmit={createTicket}>
        <input
          placeholder="Create a ticket from a customer issue"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <button className="primary-action compact" type="submit">
          <Plus size={18} aria-hidden="true" />
          Create
        </button>
      </form>

      {error ? <p className="error-text">{error}</p> : null}
      {loading ? <p className="muted">Loading tickets...</p> : null}

      <section className="ticket-list">
        {tickets.map((ticket) => (
          <Link className="ticket-row" key={ticket.id} to={`/tickets/${ticket.id}`}>
            <div>
              <h2>{ticket.title}</h2>
              <p>{ticket.ai_summary ?? "No AI summary yet"}</p>
            </div>
            <div className="ticket-meta">
              {ticket.priority ? <span className="priority">{ticket.priority}</span> : null}
              <StatusPill status={ticket.status} />
            </div>
          </Link>
        ))}
        {!loading && tickets.length === 0 ? <p className="muted">No tickets yet.</p> : null}
      </section>
    </main>
  );
}
