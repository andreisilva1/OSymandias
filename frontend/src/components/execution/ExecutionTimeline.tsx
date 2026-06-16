"use client";

import type { Task } from "@/types";
import { StatusBadge } from "@/components/jobs/JobStatusBadge";
import { formatDuration, formatDate } from "@/lib/utils";

interface Props {
  tasks: Task[];
  jobStartedAt?: string;
}

const STATUS_COLOR: Record<string, string> = {
  COMPLETED: "bg-emerald-500",
  RUNNING: "bg-blue-500 animate-pulse",
  FAILED: "bg-red-500",
  WAITING: "bg-zinc-600",
  PENDING: "bg-zinc-700",
  RETRYING: "bg-orange-500",
  READY: "bg-amber-500",
  ASSIGNED: "bg-blue-400",
  CANCELLED: "bg-zinc-600",
};

export function ExecutionTimeline({ tasks, jobStartedAt }: Props) {
  const now = Date.now();
  const start = jobStartedAt ? new Date(jobStartedAt).getTime() : now;
  const totalMs = now - start || 1;

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-medium">Execution Timeline</h2>

      <div className="space-y-3">
        {tasks.map((task) => {
          const taskStart = task.started_at ? new Date(task.started_at).getTime() : null;
          const taskEnd = task.completed_at ? new Date(task.completed_at).getTime() : now;
          const offsetPct = taskStart ? ((taskStart - start) / totalMs) * 100 : 0;
          const widthPct = taskStart ? ((taskEnd - taskStart) / totalMs) * 100 : 2;
          const duration = taskStart ? taskEnd - taskStart : undefined;

          return (
            <div key={task.id} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground w-28 truncate">{task.agent_type}</span>
                  <span className="font-medium truncate max-w-xs">{task.title}</span>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={task.status} />
                  {duration && (
                    <span className="text-muted-foreground">{formatDuration(duration)}</span>
                  )}
                </div>
              </div>
              <div className="relative h-6 bg-muted/20 rounded border border-border overflow-hidden">
                <div
                  className={`absolute h-full rounded transition-all ${STATUS_COLOR[task.status] ?? "bg-zinc-600"}`}
                  style={{
                    left: `${Math.min(offsetPct, 98)}%`,
                    width: `${Math.max(widthPct, 1)}%`,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* time axis */}
      <div className="flex justify-between text-xs text-muted-foreground pt-1 border-t border-border">
        <span>0s</span>
        <span>{formatDuration(totalMs)}</span>
      </div>
    </div>
  );
}
