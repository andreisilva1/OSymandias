import type { JobStatus, TaskStatus, AgentInstanceStatus, ToolCallStatus } from "@/types";

type AnyStatus = JobStatus | TaskStatus | AgentInstanceStatus | ToolCallStatus;

const DOT_CLASS: Record<string, string> = {
  RUNNING:          "dot-running",
  PLANNING:         "dot-planning",
  ASSIGNED:         "dot-assigned",
  READY:            "dot-ready",
  RETRYING:         "dot-retrying",
  PENDING:          "dot-pending",
  WAITING:          "dot-waiting",
  BLOCKED:          "dot-waiting",
  SUSPENDED:        "dot-waiting",
  CREATED:          "dot-idle",
  FAILED:           "dot-failed",
  CRASHED:          "dot-crashed",
  TIMEOUT:          "dot-timeout",
  PERMISSION_DENIED:"dot-red",
  COMPLETED:        "dot-completed",
  TERMINATED:       "dot-completed",
  SUCCESS:          "dot-success",
  CANCELLED:        "dot-cancelled",
  BUDGET_EXCEEDED:  "dot-failed",
  HUMAN_REVIEW:     "dot-amber",
};

const TEXT_CLASS: Record<string, string> = {
  RUNNING:          "text-green",
  PLANNING:         "text-cyan",
  ASSIGNED:         "text-cyan",
  READY:            "text-amber",
  RETRYING:         "text-amber",
  PENDING:          "text-amber",
  WAITING:          "text-muted-foreground",
  BLOCKED:          "text-amber",
  SUSPENDED:        "text-amber",
  CREATED:          "text-muted-foreground",
  FAILED:           "text-red",
  CRASHED:          "text-red",
  TIMEOUT:          "text-red",
  PERMISSION_DENIED:"text-red",
  COMPLETED:        "text-muted-foreground",
  TERMINATED:       "text-muted-foreground",
  SUCCESS:          "text-muted-foreground",
  CANCELLED:        "text-muted-foreground",
  BUDGET_EXCEEDED:  "text-red",
  HUMAN_REVIEW:     "text-amber",
};

export function StatusBadge({ status }: { status: AnyStatus }) {
  const dot = DOT_CLASS[status] ?? "dot-dim";
  const txt = TEXT_CLASS[status] ?? "text-muted-foreground";
  return (
    <span className={`inline-flex items-center gap-1.5 ${txt}`}>
      <span className={`dot ${dot}`} />
      <span className="text-[10px] font-medium tracking-wide">{status}</span>
    </span>
  );
}
