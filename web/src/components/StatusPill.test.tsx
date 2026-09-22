import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusPill } from "./StatusPill";

describe("StatusPill", () => {
  it("renders the human-readable ticket status", () => {
    render(<StatusPill status="in_progress" />);

    expect(screen.getByText("In progress")).toBeInTheDocument();
  });
});
