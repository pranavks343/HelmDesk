import { config } from "./config";

export interface TicketUpdatePayload {
  status?: string;
  priority?: string;
  ai_summary?: string;
}

export interface ApiClient {
  updateTicket(ticketId: string, payload: TicketUpdatePayload): Promise<void>;
  postMessage(ticketId: string, text: string, sender?: string): Promise<void>;
}

async function request(baseUrl: string, token: string, path: string, init: RequestInit): Promise<void> {
  const res = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Internal-Token": token,
      ...init.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`internal api call failed: ${res.status} ${body}`);
  }
}

export function createApiClient(
  baseUrl: string = config.apiInternalBaseUrl,
  token: string = config.internalServiceToken,
): ApiClient {
  return {
    async updateTicket(ticketId, payload) {
      await request(baseUrl, token, `/internal/tickets/${ticketId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    },
    async postMessage(ticketId, text, sender = "ai_agent") {
      await request(baseUrl, token, `/internal/tickets/${ticketId}/messages`, {
        method: "POST",
        body: JSON.stringify({ text, sender }),
      });
    },
  };
}
