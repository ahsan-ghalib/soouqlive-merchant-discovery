import { Badge } from "@/components/ui/badge";

const toneMap: Record<string, "default" | "success" | "warning" | "danger" | "info"> = {
  completed: "success",
  qualified: "success",
  registered: "success",
  interested: "success",
  active: "success",
  processing: "info",
  queued: "info",
  researching: "info",
  contacted: "info",
  pending: "warning",
  draft: "warning",
  follow_up: "warning",
  failed: "danger",
  cancelled: "danger",
  rejected: "danger",
  do_not_contact: "danger",
  paused: "warning",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={toneMap[status] || "default"}>{status.replaceAll("_", " ")}</Badge>;
}
