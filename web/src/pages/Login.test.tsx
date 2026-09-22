import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Login from "./Login";

function submitButton(container: HTMLElement) {
  const el = container.querySelector<HTMLButtonElement>("button.primary-action");
  if (!el) throw new Error("submit button not found");
  return el;
}

describe("Login", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ access_token: "a", refresh_token: "r", token_type: "bearer" }), {
          status: 200,
        }),
      ),
    );
  });

  it("logs in and calls onLogin with the session", async () => {
    const onLogin = vi.fn();
    const { container } = render(<Login onLogin={onLogin} />);

    await userEvent.click(submitButton(container));

    expect(onLogin).toHaveBeenCalledWith(
      expect.objectContaining({ access_token: "a", email: "demo@example.com" }),
    );
  });

  it("switches to register mode and shows a role selector", async () => {
    render(<Login onLogin={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Register" }));
    expect(screen.getByLabelText(/role/i)).toBeInTheDocument();
  });

  it("shows an error message when login fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "invalid email or password" }), { status: 401 })),
    );
    const { container } = render(<Login onLogin={vi.fn()} />);
    await userEvent.click(submitButton(container));
    expect(await screen.findByText("invalid email or password")).toBeInTheDocument();
  });
});
