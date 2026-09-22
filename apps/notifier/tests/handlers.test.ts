import { describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../src/apiClient";
import { handleClassifyTicket, handleDraftReply, type TicketRequest } from "../src/handlers";
import type { RedisPublisher } from "../src/redisPublisher";

function fakeDeps() {
  const publisher: RedisPublisher = {
    publish: vi.fn(async () => {}),
    quit: vi.fn(async () => {}),
  };
  const apiClient: ApiClient = {
    updateTicket: vi.fn(async () => {}),
    postMessage: vi.fn(async () => {}),
  };
  return { publisher, apiClient };
}

describe("handleClassifyTicket", () => {
  it("persists the ticket status/priority and publishes an update event", async () => {
    const deps = fakeDeps();
    const request: TicketRequest = {
      ticket_id: "t1",
      title: "refund please",
      context_messages: [],
      category: "billing",
      priority: "high",
      classify_confidence: 0.9,
    };

    const response = await handleClassifyTicket(request, deps);

    expect(response).toEqual({ ticket_id: "t1", category: "billing", priority: "high", confidence: 0.9 });
    expect(deps.apiClient.updateTicket).toHaveBeenCalledWith("t1", { status: "triaged", priority: "high" });
    expect(deps.publisher.publish).toHaveBeenCalledWith(
      "ticket.updated",
      expect.objectContaining({ ticket_id: "t1", type: "updated", category: "billing" }),
    );
  });

  it("defaults to general/low/0 when fields are missing", async () => {
    const deps = fakeDeps();
    const response = await handleClassifyTicket({ ticket_id: "t2", title: "x", context_messages: [] }, deps);
    expect(response).toEqual({ ticket_id: "t2", category: "general", priority: "low", confidence: 0 });
  });
});

describe("handleDraftReply", () => {
  it("auto-resolve => persists status resolved, posts the draft as a message", async () => {
    const deps = fakeDeps();
    const request: TicketRequest = {
      ticket_id: "t3",
      title: "refund please",
      context_messages: [],
      draft_text: "Refund processed automatically.",
      draft_confidence: 0.9,
      auto_resolve: true,
    };

    const response = await handleDraftReply(request, deps);

    expect(response.auto_resolve).toBe(true);
    expect(deps.apiClient.updateTicket).toHaveBeenCalledWith("t3", {
      status: "resolved",
      ai_summary: "Refund processed automatically.",
    });
    expect(deps.apiClient.postMessage).toHaveBeenCalledWith(
      "t3",
      "Refund processed automatically.",
      "ai_agent",
    );
    expect(deps.publisher.publish).toHaveBeenCalledWith("ticket.message", expect.objectContaining({ ticket_id: "t3" }));
  });

  it("not auto-resolved => persists status triaged, still posts the draft for a human to review", async () => {
    const deps = fakeDeps();
    const request: TicketRequest = {
      ticket_id: "t4",
      title: "something",
      context_messages: [],
      draft_text: "Here's a possible answer.",
      draft_confidence: 0.6,
      auto_resolve: false,
    };

    const response = await handleDraftReply(request, deps);

    expect(response.auto_resolve).toBe(false);
    expect(deps.apiClient.updateTicket).toHaveBeenCalledWith("t4", {
      status: "triaged",
      ai_summary: "Here's a possible answer.",
    });
  });

  it("does not post a message when there is no draft text (low-confidence skip path)", async () => {
    const deps = fakeDeps();
    const request: TicketRequest = { ticket_id: "t5", title: "x", context_messages: [] };

    await handleDraftReply(request, deps);

    expect(deps.apiClient.postMessage).not.toHaveBeenCalled();
    expect(deps.publisher.publish).not.toHaveBeenCalledWith("ticket.message", expect.anything());
  });
});
