"use client";

import type { Task } from "@/types";
import { StatusBadge } from "@/components/jobs/JobStatusBadge";
import { formatDuration } from "@/lib/utils";

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
  HUMAN_REVIEW: "bg-amber-400",
};

interface TreeNode {
  task: Task;
  children: TreeNode[];
}

function buildTree(tasks: Task[]): TreeNode[] {
  const byId = new Map(tasks.map((t) => [t.id, { task: t, children: [] as TreeNode[] }]));
  const roots: TreeNode[] = [];
  for (const node of byId.values()) {
    const parentId = node.task.parent_task_id;
    if (parentId && byId.has(parentId)) {
      byId.get(parentId)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

function TaskRow({
  node,
  depth,
  start,
  totalMs,
  now,
}: {
  node: TreeNode;
  depth: number;
  start: number;
  totalMs: number;
  now: number;
}) {
  const { task } = node;
  const taskStart = task.started_at ? new Date(task.started_at).getTime() : null;
  const taskEnd = task.completed_at ? new Date(task.completed_at).getTime() : now;
  const offsetPct = taskStart ? ((taskStart - start) / totalMs) * 100 : 0;
  const widthPct = taskStart ? ((taskEnd - taskStart) / totalMs) * 100 : 2;
  const duration = taskStart ? taskEnd - taskStart : undefined;

  return (
    <>
      <div className="space-y-1" style={{ paddingLeft: depth * 20 }}>
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            {depth > 0 && <span className="text-muted-foreground">↳</span>}
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
      {node.children.map((child) => (
        <TaskRow
          key={child.task.id}
          node={child}
          depth={depth + 1}
          start={start}
          totalMs={totalMs}
          now={now}
        />
      ))}
    </>
  );
}

export function ExecutionTimeline({ tasks, jobStartedAt }: Props) {
  const now = Date.now();
  const start = jobStartedAt ? new Date(jobStartedAt).getTime() : now;
  const totalMs = now - start || 1;
  const tree = buildTree(tasks);

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-medium">Execution Timeline</h2>

      <div className="space-y-3">
        {tree.map((node) => (
          <TaskRow
            key={node.task.id}
            node={node}
            depth={0}
            start={start}
            totalMs={totalMs}
            now={now}
          />
        ))}
      </div>

      <div className="flex justify-between text-xs text-muted-foreground pt-1 border-t border-border">
        <span>0s</span>
        <span>{formatDuration(totalMs)}</span>
      </div>
    </div>
  );
}
