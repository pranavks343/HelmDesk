import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "./Dashboard";
import type { Session } from "../App";

const session: Session = {
  access_token: "a",
  refresh_token: "r",
  token_type: "bearer",
  email: "demo@example.com",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse([])));
  });

  it("loads and renders an empty ticket list", async () => {
    render(
      <MemoryRouter>
        <Dashboard session={session} onLogout={vi.fn()} />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/no tickets yet/i)).toBeInTheDocument();
  });

  it("creates a ticket and adds it to the list", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/tickets") && init?.method === "POST") {
        return jsonResponse({
          id: "t1",
          user_id: "u1",
          title: "Printer on fire",
          status: "open",
          priority: null,
          ai_summary: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <Dashboard session={session} onLogout={vi.fn()} />
      </MemoryRouter>,
    );
    await screen.findByText(/no tickets yet/i);

    await userEvent.type(
      screen.getByPlaceholderText(/create a ticket/i),
      "Printer on fire",
    );
    await userEvent.click(screen.getByRole("button", { name: /create/i }));

    expect(await screen.findByText("Printer on fire")).toBeInTheDocument();
  });

  it("calls onLogout when the sign-out button is clicked", async () => {
    const onLogout = vi.fn();
    render(
      <MemoryRouter>
        <Dashboard session={session} onLogout={onLogout} />
      </MemoryRouter>,
    );
    await screen.findByText(/no tickets yet/i);
    await userEvent.click(screen.getByTitle(/sign out/i));
    expect(onLogout).toHaveBeenCalled();
  });
});
