"use client";

import type { Event } from "@/types";
import { formatDate } from "@/lib/utils";
import { cn } from "@/lib/utils";

const EVENT_COLOR: Record<string, string> = {
  JOB_CREATED: "text-zinc-400",
  JOB_STARTED: "text-blue-400",
  JOB_COMPLETED: "text-emerald-400",
  JOB_FAILED: "text-red-400",
  JOB_CANCELLED: "text-zinc-400",
  JOB_BUDGET_EXCEEDED: "text-red-500",
  TASK_CREATED: "text-zinc-400",
  TASK_READY: "text-amber-400",
  TASK_COMPLETED: "text-emerald-400",
  TASK_FAILED: "text-red-400",
  TASK_AWAITING_APPROVAL: "text-amber-400",
  TASK_APPROVED: "text-emerald-300",
  AGENT_SPAWNED: "text-blue-300",
  AGENT_RUNNING: "text-blue-400",
  AGENT_TERMINATED: "text-emerald-300",
  AGENT_CRASHED: "text-red-400",
  LLM_CALL_STARTED: "text-violet-400",
  LLM_CALL_COMPLETED: "text-violet-300",
  TOOL_CALL_STARTED: "text-amber-400",
  TOOL_CALL_COMPLETED: "text-amber-300",
  TOOL_CALL_FAILED: "text-red-400",
  TOOL_PERMISSION_DENIED: "text-red-500",
  MESSAGE_SENT: "text-cyan-400",
  MEMORY_WRITE: "text-indigo-400",
  MEMORY_READ: "text-indigo-300",
  EVALUATION_COMPLETED: "text-pink-400",
};

interface Props {
  events: Event[];
}

export function EventStream({ events }: Props) {
  const sorted = [...events].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">Event Log</h2>
        <span className="text-xs text-muted-foreground">{events.length} events</span>
      </div>

      <div className="rounded-lg border border-border overflow-hidden bg-black/20">
        <div className="divide-y divide-border">
          {sorted.map((event) => (
            <div
              key={event.id}
              className="flex items-start gap-3 px-4 py-2.5 hover:bg-accent/20 transition-colors event-row-enter"
            >
              <span className="text-xs text-muted-foreground whitespace-nowrap pt-0.5 w-20 shrink-0">
                {new Date(event.timestamp).toLocaleTimeString()}
              </span>
              <span
                className={cn(
                  "text-xs font-mono font-medium w-44 shrink-0 pt-0.5",
                  EVENT_COLOR[event.event_type] ?? "text-muted-foreground"
                )}
              >
                {event.event_type}
              </span>
              <div className="flex-1 min-w-0">
                <span className="text-xs text-muted-foreground truncate block">
                  {JSON.stringify(event.payload)}
                </span>
              </div>
              {event.tokens_used && (
                <span className="text-xs text-muted-foreground shrink-0">{event.tokens_used}t</span>
              )}
              {event.duration_ms && (
                <span className="text-xs text-muted-foreground shrink-0">{event.duration_ms}ms</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
