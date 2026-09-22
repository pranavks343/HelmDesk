import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, LogOut, Send } from "lucide-react";
import { api, type Message, type Ticket } from "../api/client";
import type { Session } from "../App";
import { StatusPill } from "../components/StatusPill";
import { useWebSocket } from "../hooks/useWebSocket";

type Props = {
  session: Session;
  onLogout: () => void;
};

export default function TicketDetail({ session, onLogout }: Props) {
  const { ticketId } = useParams();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { state, events } = useWebSocket(ticketId, session.access_token);

  const loadTicket = useCallback(async () => {
    if (!ticketId) {
      return;
    }
    setError(null);
    try {
      const [nextTicket, nextMessages] = await Promise.all([
        api.getTicket(session.access_token, ticketId),
        api.listMessages(session.access_token, ticketId),
      ]);
      setTicket(nextTicket);
      setMessages(nextMessages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load ticket");
    }
  }, [session.access_token, ticketId]);

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (!ticketId || !draft.trim()) {
      return;
    }
    try {
      const message = await api.postMessage(session.access_token, ticketId, draft.trim());
      setMessages((current) => [...current, message]);
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send message");
    }
  }

  useEffect(() => {
    void loadTicket();
  }, [loadTicket]);

  useEffect(() => {
    for (const event of events) {
      if (event.type === "updated") {
        setTicket((current) => (current ? { ...current, ...event } : current));
      }
      if (event.type === "message" && event.text && event.sender && event.ticket_id) {
        setMessages((current) => [
          ...current,
          {
            ticket_id: event.ticket_id,
            sender: event.sender ?? "system",
            text: event.text ?? "",
            created_at: new Date().toISOString(),
          },
        ]);
      }
    }
  }, [events]);

  return (
    <main className="app-shell detail-shell">
      <header className="topbar">
        <div className="breadcrumb-title">
          <Link className="icon-button" to="/tickets" title="Back to tickets">
            <ArrowLeft size={18} aria-hidden="true" />
          </Link>
          <div>
            <p className="eyebrow">Ticket detail</p>
            <h1>{ticket?.title ?? "Loading..."}</h1>
          </div>
        </div>
        <div className="topbar-actions">
          <span className={`socket-dot socket-${state}`}>{state}</span>
          <button className="icon-button" onClick={onLogout} title="Sign out" type="button">
            <LogOut size={18} aria-hidden="true" />
          </button>
        </div>
      </header>

      {error ? <p className="error-text">{error}</p> : null}

      {ticket ? (
        <section className="detail-grid">
          <aside className="side-panel">
            <StatusPill status={ticket.status} />
            <dl>
              <div>
                <dt>Priority</dt>
                <dd>{ticket.priority ?? "Unscored"}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{new Date(ticket.updated_at).toLocaleString()}</dd>
              </div>
              <div>
                <dt>AI summary</dt>
                <dd>{ticket.ai_summary ?? "Pending agent triage"}</dd>
              </div>
            </dl>
          </aside>

          <section className="conversation">
            <div className="message-list">
              {messages.map((message, index) => (
                <article className="message" key={`${message.created_at}-${index}`}>
                  <div>
                    <strong>{message.sender}</strong>
                    <time>{new Date(message.created_at).toLocaleString()}</time>
                  </div>
                  <p>{message.text}</p>
                </article>
              ))}
              {messages.length === 0 ? <p className="muted">No messages yet.</p> : null}
            </div>

            <form className="message-composer" onSubmit={sendMessage}>
              <textarea
                placeholder="Add a customer-visible message"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
              />
              <button className="primary-action compact" type="submit">
                <Send size={18} aria-hidden="true" />
                Send
              </button>
            </form>
          </section>
        </section>
      ) : null}
    </main>
  );
}
