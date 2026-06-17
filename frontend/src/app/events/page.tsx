"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useEvents } from "@/hooks/useJobData";
import { Loader2, Pause, Play } from "lucide-react";

const EVENT_COLORS: Record<string, string> = {
  // Job lifecycle
  JOB_CREATED: "#5090A8", JOB_STARTED: "#5090A8",
  JOB_COMPLETED: "#60A890", JOB_FAILED: "#C06070", JOB_CANCELLED: "#384858",
  // Task lifecycle
  TASK_CREATED: "#384858", TASK_READY: "#5090A8", TASK_STARTED: "#C8A040",
  TASK_COMPLETED: "#60A890", TASK_FAILED: "#C06070", TASK_RETRYING: "#C8A040",
  // Agent lifecycle
  AGENT_SPAWNED: "#7870A0", AGENT_RUNNING: "#7870A0",
  AGENT_TERMINATED: "#384858", AGENT_CRASHED: "#C06070",
  AGENT_STARTED: "#7870A0", AGENT_COMPLETED: "#60A890",
  // LLM calls
  LLM_CALL_STARTED: "#C8A040", LLM_CALL_COMPLETED: "#60A890", LLM_CALL_FAILED: "#C06070",
  // Tool calls
  TOOL_CALL_STARTED: "#C8A040", TOOL_CALL_COMPLETED: "#60A890", TOOL_CALL_FAILED: "#C06070",
  // Memory / messages
  MEMORY_WRITE: "#5090A8", MEMORY_READ: "#384858", MESSAGE_SENT: "#5090A8",
  // Evaluation
  EVALUATION_STARTED: "#7870A0", EVALUATION_COMPLETED: "#60A890",
};

const EVENT_TYPES = [
  "ALL",
  "JOB_CREATED", "JOB_COMPLETED", "JOB_FAILED",
  "TASK_STARTED", "TASK_COMPLETED", "TASK_FAILED",
  "AGENT_SPAWNED", "AGENT_TERMINATED", "AGENT_CRASHED",
  "LLM_CALL_STARTED", "LLM_CALL_COMPLETED",
  "TOOL_CALL_STARTED", "TOOL_CALL_COMPLETED",
];

export default function EventStreamPage() {
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [paused, setPaused] = useState(false);
  const [displayedEvents, setDisplayedEvents] = useState<typeof events>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const { data: events = [], isLoading } = useEvents({ limit: 200 });

  // Update displayed events unless paused
  useEffect(() => {
    if (!paused) setDisplayedEvents(events);
  }, [events, paused]);

  const filtered = typeFilter === "ALL" ? displayedEvents : displayedEvents.filter((e) => e.event_type === typeFilter);

  // Auto-scroll to bottom when new events arrive and not paused
  useEffect(() => {
    if (!paused && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [filtered.length, paused]);

  const totalTokens = filtered.reduce((s, e) => s + (e.tokens_used ?? 0), 0);
  const totalCost = filtered.reduce((s, e) => s + (e.estimated_cost ?? 0), 0);

  return (
    <div className="flex flex-col h-full">
      {/* Topbar */}
      <div className="page-topbar">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: paused ? "#C8A040" : "#60A890", boxShadow: paused ? "0 0 6px rgba(200,160,64,0.5)" : "0 0 6px rgba(96,168,144,0.5)", flexShrink: 0 }} />
            <div className="page-title">Event Log</div>
          </div>
          <div className="page-sub">{filtered.length} events{paused ? " · paused" : " · live"}</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {isLoading && !paused && <Loader2 style={{ width: 13, height: 13, color: "#607080" }} className="animate-spin" />}
          <button
            onClick={() => setPaused((p) => !p)}
            className="btn btn-ghost"
            style={{ gap: 5, fontSize: 11 }}
          >
            {paused
              ? <><Play style={{ width: 11, height: 11 }} /> Resume</>
              : <><Pause style={{ width: 11, height: 11 }} /> Pause</>
            }
          </button>
        </div>
      </div>

      {/* Type filter */}
      <div className="filter-bar" style={{ flexWrap: "wrap", gap: 4 }}>
        {EVENT_TYPES.map((t) => (
          <button key={t} onClick={() => setTypeFilter(t)}
            style={{
              fontSize: 10, padding: "4px 10px", borderRadius: 5, border: "1px solid transparent",
              background: typeFilter === t ? "rgba(200,160,64,0.08)" : "transparent",
              color: typeFilter === t ? "#C8A040" : "#607080",
              borderColor: typeFilter === t ? "rgba(200,160,64,0.2)" : "transparent",
              cursor: "pointer", transition: "all 0.15s",
              fontFamily: "inherit",
            }}
            onMouseEnter={(e) => { if (typeFilter !== t) e.currentTarget.style.color = "#D8E0E8"; }}
            onMouseLeave={(e) => { if (typeFilter !== t) e.currentTarget.style.color = "#607080"; }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Column headers */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "130px 96px 190px 88px 1fr 64px",
        gap: 12, padding: "6px 20px",
        fontSize: 9, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase",
        color: "#283040", borderBottom: "1px solid #1E2830",
        background: "rgba(12,16,24,0.8)", flexShrink: 0,
      }}>
        <span>Timestamp</span><span>Job</span><span>Event Type</span>
        <span>Agent</span><span>Payload</span><span>Dur</span>
      </div>

      {/* Rows */}
      <div ref={listRef} style={{ flex: 1, overflowY: "auto" }}>
        {filtered.length === 0 && !isLoading && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "64px 0", fontSize: 12, color: "#283040" }}>
            no events — run a process to generate events
          </div>
        )}

        {filtered.map((ev) => {
          const ts = new Date(ev.timestamp);
          const timeStr = `${String(ts.getHours()).padStart(2, "0")}:${String(ts.getMinutes()).padStart(2, "0")}:${String(ts.getSeconds()).padStart(2, "0")}.${String(ts.getMilliseconds()).padStart(3, "0")}`;
          const evColor = EVENT_COLORS[ev.event_type] ?? "#384858";

          const payloadText = ev.payload?.tool_name
            ? `tool=${ev.payload.tool_name}`
            : ev.payload?.error
            ? String(ev.payload.error).slice(0, 60)
            : ev.payload?.score !== undefined
            ? `score=${ev.payload.score}`
            : JSON.stringify(ev.payload).slice(0, 60);

          const isError = !!(ev.payload?.error);

          return (
            <div key={ev.id} style={{
              display: "grid",
              gridTemplateColumns: "130px 96px 190px 88px 1fr 64px",
              gap: 12, padding: "7px 20px",
              borderBottom: "1px solid rgba(30,40,48,0.4)",
              alignItems: "center", transition: "background 0.1s",
            }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#182028")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <span style={{ fontSize: 11, color: "#384858", fontVariantNumeric: "tabular-nums", fontFamily: "monospace" }}>
                {timeStr}
              </span>

              <span style={{ fontSize: 10, fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {ev.job_id ? (
                  <Link href={`/jobs/${ev.job_id}`} style={{ color: "#5090A8", textDecoration: "none" }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "#C8A040")}
                    onMouseLeave={(e) => (e.currentTarget.style.color = "#5090A8")}
                  >
                    {ev.job_id.slice(0, 8)}
                  </Link>
                ) : (
                  <span style={{ color: "#283040" }}>system</span>
                )}
              </span>

              <span style={{ fontSize: 11, fontWeight: 500, color: evColor, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {ev.event_type}
              </span>

              <span style={{ fontSize: 10, fontFamily: "monospace", color: "#384858", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {ev.agent_instance_id ? ev.agent_instance_id.slice(0, 8) : "—"}
              </span>

              <span style={{ fontSize: 10, fontFamily: "monospace", color: isError ? "#C06070" : "#607080", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {payloadText}
              </span>

              <span style={{ fontSize: 10, color: "#384858", fontVariantNumeric: "tabular-nums", fontFamily: "monospace" }}>
                {ev.duration_ms != null ? `${ev.duration_ms}ms` : "—"}
              </span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Footer */}
      {filtered.length > 0 && (
        <div style={{
          borderTop: "1px solid #1E2830", padding: "8px 20px",
          display: "flex", alignItems: "center", gap: 20,
          fontSize: 10, color: "#607080", background: "rgba(12,16,24,0.8)",
          flexShrink: 0,
        }}>
          <span>
            tokens: <span style={{ color: "#D8E0E8", fontVariantNumeric: "tabular-nums" }}>{totalTokens.toLocaleString()}</span>
          </span>
          <span>
            est. cost: <span style={{ color: "#C8A040", fontVariantNumeric: "tabular-nums" }}>${totalCost.toFixed(4)}</span>
          </span>
          <span style={{ marginLeft: "auto", color: "#283040" }}>
            {filtered.length} events · {paused ? "paused" : "refreshes every 3s"}
          </span>
        </div>
      )}
    </div>
  );
}
