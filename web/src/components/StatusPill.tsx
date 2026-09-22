import type { TicketStatus } from "../api/client";

type Props = {
  status: TicketStatus;
};

const labels: Record<TicketStatus, string> = {
  open: "Open",
  triaged: "Triaged",
  in_progress: "In progress",
  resolved: "Resolved",
};

export function StatusPill({ status }: Props) {
  return <span className={`status-pill status-${status}`}>{labels[status]}</span>;
}
