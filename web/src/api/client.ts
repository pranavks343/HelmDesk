export type Role = "customer" | "agent" | "admin";
export type TicketStatus = "open" | "triaged" | "in_progress" | "resolved";

export type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
};

export type Ticket = {
  id: string;
  user_id: string;
  title: string;
  status: TicketStatus;
  priority: string | null;
  ai_summary: string | null;
  created_at: string;
  updated_at: string;
};

export type Message = {
  ticket_id: string;
  sender: string;
  text: string;
  created_at: string;
};

export type TicketEvent = {
  ticket_id: string;
  type: "created" | "updated" | "message" | string;
  title?: string;
  status?: TicketStatus;
  priority?: string | null;
  ai_summary?: string | null;
  sender?: string;
  text?: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type RequestOptions = RequestInit & {
  token?: string | null;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch {
    throw new Error(`Cannot reach the API at ${API_BASE_URL}. Start the API and its database services.`);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // Keep the HTTP status text when the API returns a non-JSON error.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function wsUrl(ticketId: string, token: string): string {
  const base = new URL(API_BASE_URL);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  base.pathname = `/ws/tickets/${ticketId}`;
  base.searchParams.set("token", token);
  return base.toString();
}

export const api = {
  login(email: string, password: string) {
    return request<AuthTokens>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  register(email: string, password: string, role: Role = "customer") {
    return request<{ id: string; email: string; role: Role }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, role }),
    });
  },

  refresh(refreshToken: string) {
    return request<AuthTokens>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  },

  listTickets(token: string) {
    return request<Ticket[]>("/tickets", { token });
  },

  createTicket(token: string, title: string) {
    return request<Ticket>("/tickets", {
      method: "POST",
      token,
      body: JSON.stringify({ title }),
    });
  },

  getTicket(token: string, id: string) {
    return request<Ticket>(`/tickets/${id}`, { token });
  },

  updateTicket(token: string, id: string, payload: Partial<Pick<Ticket, "status" | "priority" | "ai_summary">>) {
    return request<Ticket>(`/tickets/${id}`, {
      method: "PATCH",
      token,
      body: JSON.stringify(payload),
    });
  },

  listMessages(token: string, ticketId: string) {
    return request<Message[]>(`/tickets/${ticketId}/messages`, { token });
  },

  postMessage(token: string, ticketId: string, text: string) {
    return request<Message>(`/tickets/${ticketId}/messages`, {
      method: "POST",
      token,
      body: JSON.stringify({ text }),
    });
  },
};
