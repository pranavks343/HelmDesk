import { afterEach, describe, expect, it, vi } from "vitest";
import { createApiClient } from "../src/apiClient";

describe("apiClient", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the internal token header and PATCH body on updateTicket", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const client = createApiClient("http://api.local", "secret-token");
    await client.updateTicket("t1", { status: "resolved" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.local/internal/tickets/t1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ status: "resolved" }),
        headers: expect.objectContaining({ "X-Internal-Token": "secret-token" }),
      }),
    );
  });

  it("throws when the api responds with a non-2xx status", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 500 })));
    const client = createApiClient("http://api.local", "secret-token");
    await expect(client.updateTicket("t1", { status: "resolved" })).rejects.toThrow(/500/);
  });

  it("posts a message with the given sender", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    const client = createApiClient("http://api.local", "secret-token");
    await client.postMessage("t1", "hello", "ai_agent");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.local/internal/tickets/t1/messages",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ text: "hello", sender: "ai_agent" }) }),
    );
  });
});
