import { useEffect, useState } from "react";
import type { TicketEvent } from "../api/client";
import { wsUrl } from "../api/client";

export type SocketState = "idle" | "connecting" | "open" | "closed" | "error";

export function useWebSocket(ticketId: string | undefined, token: string | null) {
  const [state, setState] = useState<SocketState>("idle");
  const [events, setEvents] = useState<TicketEvent[]>([]);

  useEffect(() => {
    if (!ticketId || !token) {
      setState("idle");
      return;
    }

    setState("connecting");
    const socket = new WebSocket(wsUrl(ticketId, token));

    socket.addEventListener("open", () => setState("open"));
    socket.addEventListener("close", () => setState("closed"));
    socket.addEventListener("error", () => setState("error"));
    socket.addEventListener("message", (message) => {
      try {
        setEvents((current) => [...current, JSON.parse(message.data) as TicketEvent]);
      } catch {
        setEvents((current) => [...current, { ticket_id: ticketId, type: "message", text: message.data }]);
      }
    });

    return () => socket.close();
  }, [ticketId, token]);

  return { state, events, clearEvents: () => setEvents([]) };
}
