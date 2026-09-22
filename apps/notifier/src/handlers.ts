/**
 * The actual relay logic, kept separate from gRPC server plumbing (server.ts) so it's testable
 * with plain objects and fake publisher/apiClient doubles - no gRPC harness needed in tests.
 *
 * notifier doesn't classify or draft anything itself; it just republishes what agent-worker
 * already computed (via Redis, for the live WS feed) and persists it (via api's internal
 * endpoints). See proto/ticket.proto's own comment for why both RPCs share one request shape.
 */

import type { ApiClient } from "./apiClient";
import { CHANNEL_TICKET_MESSAGE, CHANNEL_TICKET_UPDATED, type RedisPublisher } from "./redisPublisher";

export interface KBHit {
  doc_id: string;
  title: string;
  snippet: string;
  score: number;
}

export interface TicketRequest {
  ticket_id: string;
  title: string;
  context_messages: string[];
  category?: string;
  priority?: string;
  classify_confidence?: number;
  kb_hits?: KBHit[];
  draft_text?: string;
  draft_confidence?: number;
  auto_resolve?: boolean;
}

export interface ClassifyResponse {
  ticket_id: string;
  category: string;
  priority: string;
  confidence: number;
}

export interface DraftResponse {
  ticket_id: string;
  draft_text: string;
  confidence: number;
  auto_resolve: boolean;
}

export interface Deps {
  publisher: RedisPublisher;
  apiClient: ApiClient;
}

export async function handleClassifyTicket(
  request: TicketRequest,
  { publisher, apiClient }: Deps,
): Promise<ClassifyResponse> {
  const category = request.category ?? "general";
  const priority = request.priority ?? "low";
  const confidence = request.classify_confidence ?? 0;

  await apiClient.updateTicket(request.ticket_id, { status: "triaged", priority });
  await publisher.publish(CHANNEL_TICKET_UPDATED, {
    ticket_id: request.ticket_id,
    type: "updated",
    status: "triaged",
    priority,
    category,
  });

  return { ticket_id: request.ticket_id, category, priority, confidence };
}

export async function handleDraftReply(
  request: TicketRequest,
  { publisher, apiClient }: Deps,
): Promise<DraftResponse> {
  const draftText = request.draft_text ?? "";
  const confidence = request.draft_confidence ?? 0;
  const autoResolve = request.auto_resolve ?? false;
  const status = autoResolve ? "resolved" : "triaged";

  await apiClient.updateTicket(request.ticket_id, {
    status,
    ai_summary: draftText,
  });
  if (draftText) {
    await apiClient.postMessage(request.ticket_id, draftText, "ai_agent");
  }

  await publisher.publish(CHANNEL_TICKET_UPDATED, {
    ticket_id: request.ticket_id,
    type: "updated",
    status,
    ai_summary: draftText,
  });
  if (draftText) {
    await publisher.publish(CHANNEL_TICKET_MESSAGE, {
      ticket_id: request.ticket_id,
      type: "message",
      sender: "ai_agent",
      text: draftText,
    });
  }

  return { ticket_id: request.ticket_id, draft_text: draftText, confidence, auto_resolve: autoResolve };
}
