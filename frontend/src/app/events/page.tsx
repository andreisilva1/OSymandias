"use client";

import { useState } from "react";
import { useEvents } from "@/hooks/useJobData";
import { Loader2 } from "lucide-react";

const EVENT_COLORS: Record<string, string> = {
  JOB_CREATED: "text-cyan", JOB_STARTED: "text-cyan", JOB_COMPLETED: "text-green",
  JOB_CANCELLED: "text-muted-foreground", JOB_FAILED: "text-red",
  TASK_CREATED: "text-muted-foreground", TASK_ASSIGNED: "text-cyan",
  TASK_COMPLETED: "text-green", TASK_FAILED: "text-red", TASK_RETRYING: "text-amber",
  AGENT_STARTED: "text-purple", AGENT_ITERATION: "text-muted-foreground",
  AGENT_COMPLETED: "text-green", AGENT_CRASHED: "text-red", AGENT_HEARTBEAT: "text-muted-foreground/40",
  TOOL_CALLED: "text-amber", TOOL_SUCCEEDED: "text-green", TOOL_FAILED: "text-red",
  EVALUATION_STARTED: "text-purple", EVALUATION_COMPLETED: "text-green",
  MEMORY_WRITE: "text-cyan", MEMORY_READ: "text-muted-foreground",
  MESSAGE_SENT: "text-blue-400",
};

const EVENT_TYPES = [
  "ALL", "JOB_CREATED", "JOB_COMPLETED", "JOB_FAILED",
  "AGENT_STARTED", "AGENT_COMPLETED", "AGENT_CRASHED",
  "TOOL_CALLED", "TOOL_FAILED", "TASK_COMPLETED", "TASK_FAILED",
];

export default function EventStreamPage() {
  const [typeFilter, setTypeFilter] = useState("ALL");
  const { data: events = [], isLoading } = useEvents({ limit: 100 });

  const filtered = typeFilter === "ALL" ? events : events.filter((e) => e.event_type === typeFilter);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border shrink-0">
        <div>
          <div className="os-label mb-0.5">OBSERVABILITY / EVENT STREAM</div>
          <div className="flex items-center gap-2">
            <span className="dot dot-running" style={{ width: 5, height: 5 }} />
            <h1 className="text-[15px] font-semibold text-bright">Event Log</h1>
          </div>
        </div>
        <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
          {isLoading && <Loader2 className="w-3 h-3 animate-spin" />}
          <span className="tabular">{filtered.length} events</span>
        </div>
      </div>

      {/* Type filter */}
      <div className="flex flex-wrap gap-px px-5 py-2 border-b border-border shrink-0 bg-card/50">
        {EVENT_TYPES.map((t) => (
          <button key={t} onClick={() => setTypeFilter(t)}
            className={`px-2.5 py-1.5 text-[10px] tracking-wide transition-colors rounded-sm ${
              typeFilter === t
                ? "text-foreground bg-accent border-b-2 border-[#C9A84C]"
                : "text-muted-foreground hover:text-foreground hover:bg-accent/40"
            }`}>
            {t}
          </button>
        ))}
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[130px_90px_180px_80px_1fr_60px] gap-3 px-5 py-2 os-label border-b border-border bg-background/95 sticky top-0 select-none">
        <span>TIMESTAMP</span><span>JOB</span><span>EVENT TYPE</span>
        <span>AGENT</span><span>PAYLOAD</span><span>DUR</span>
      </div>

      {/* Event rows */}
      <div className="flex-1 overflow-auto divide-y divide-border/30">
        {filtered.length === 0 && !isLoading && (
          <div className="flex items-center justify-center py-16 text-[12px] text-muted-foreground/30">
            no events — run a process to generate events
          </div>
        )}
        {filtered.map((ev) => {
          const ts = new Date(ev.timestamp);
          const timeStr = `${String(ts.getHours()).padStart(2,"0")}:${String(ts.getMinutes()).padStart(2,"0")}:${String(ts.getSeconds()).padStart(2,"0")}.${String(ts.getMilliseconds()).padStart(3,"0")}`;
          const evColor = EVENT_COLORS[ev.event_type] ?? "text-muted-foreground";

          return (
            <div key={ev.id}
              className="grid grid-cols-[130px_90px_180px_80px_1fr_60px] gap-3 px-5 py-2 hover:bg-accent/50 transition-colors items-center event-row-enter">
              <span className="text-[11px] text-muted-foreground/50 tabular font-mono">{timeStr}</span>
              <span className="pid tabular truncate">
                {ev.job_id ? ev.job_id.slice(0, 8) : <span className="text-muted-foreground/30">system</span>}
              </span>
              <span className={`text-[11px] font-medium ${evColor}`}>{ev.event_type}</span>
              <span className="pid truncate">
                {ev.agent_instance_id ? ev.agent_instance_id.slice(0, 8) : "—"}
              </span>
              <span className="text-[11px] text-muted-foreground/50 truncate font-mono">
                {ev.payload?.tool_name
                  ? `tool=${ev.payload.tool_name}`
                  : ev.payload?.error
                  ? <span className="text-red">{String(ev.payload.error).slice(0, 60)}</span>
                  : ev.payload?.score !== undefined
                  ? `score=${ev.payload.score}`
                  : JSON.stringify(ev.payload).slice(0, 60)}
              </span>
              <span className="text-[11px] text-muted-foreground/30 tabular font-mono">
                {ev.duration_ms != null ? `${ev.duration_ms}ms` : "—"}
              </span>
            </div>
          );
        })}
      </div>

      {/* Cost/token summary */}
      {filtered.length > 0 && (
        <div className="border-t border-border px-5 py-2 flex items-center gap-6 text-[11px] text-muted-foreground shrink-0 bg-card/50">
          <span>
            tokens: <span className="text-foreground tabular font-mono">
              {filtered.reduce((s, e) => s + (e.tokens_used ?? 0), 0).toLocaleString()}
            </span>
          </span>
          <span>
            est. cost: <span className="text-amber tabular font-mono">
              ${filtered.reduce((s, e) => s + (e.estimated_cost ?? 0), 0).toFixed(4)}
            </span>
          </span>
          <span className="ml-auto text-muted-foreground/30">
            showing {filtered.length} events · refreshes every 3s
          </span>
        </div>
      )}
    </div>
  );
}
