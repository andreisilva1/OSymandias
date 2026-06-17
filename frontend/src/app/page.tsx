"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useJobs, useAgents, useMetrics, useEvents } from "@/hooks/useJobData";
import { formatTokens, formatCost, formatRelative } from "@/lib/utils";
import { ChevronRight, Plus, Loader2 } from "lucide-react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { JobStatus } from "@/types";

/* ── Uptime counter ─────────────────────────────────────── */
function useUptime() {
  const [start] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed(Date.now() - start), 1000);
    return () => clearInterval(id);
  }, [start]);
  const s = Math.floor(elapsed / 1000);
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  if (h > 0) return `${h}h ${m % 60}m`;
  if (m > 0) return `${m}m ${s % 60}s`;
  return `${s}s`;
}

/* ── Gauge component ────────────────────────────────────── */
function Gauge({ pct, color = "gauge-cyan" }: { pct: number; color?: string }) {
  return (
    <div className="gauge flex-1">
      <div className={`gauge-fill ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

/* ── Event type coloring ────────────────────────────────── */
const EVENT_COLOR: Record<string, string> = {
  JOB_CREATED: "text-cyan", JOB_STARTED: "text-cyan", JOB_COMPLETED: "text-green",
  JOB_FAILED: "text-red", TASK_CREATED: "text-muted-foreground", TASK_COMPLETED: "text-green",
  TASK_FAILED: "text-red", AGENT_STARTED: "text-purple", AGENT_ITERATION: "text-muted-foreground",
  AGENT_COMPLETED: "text-green", AGENT_CRASHED: "text-red", TOOL_CALLED: "text-amber",
  TOOL_SUCCEEDED: "text-green", TOOL_FAILED: "text-red",
};

/* ── Spawn process modal ────────────────────────────────── */
function QuickJobModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("NORMAL");
  const [payload, setPayload] = useState("{}");
  const [err, setErr] = useState("");

  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      api.jobs.create({ title, description: description || undefined, priority, input_payload: JSON.parse(payload) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["jobs"] }); onClose(); },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("");
    try { JSON.parse(payload); } catch { setErr("Invalid JSON in payload"); return; }
    mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="os-card p-6 w-[460px] shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div style={{ fontSize: 15, fontWeight: 600, color: "#D8E0E8", marginBottom: 20, letterSpacing: "-0.3px" }}>
          Spawn Process
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="os-label block mb-1.5">TITLE</label>
            <input autoFocus required value={title} onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}
              className="os-input" placeholder="process title..." />
          </div>
          <div>
            <label className="os-label block mb-1.5">DESCRIPTION</label>
            <input value={description} onChange={(e) => setDescription(e.target.value)}
              className="os-input" placeholder="optional..." />
          </div>
          <div>
            <label className="os-label block mb-1.5">PRIORITY</label>
            <select value={priority} onChange={(e) => setPriority(e.target.value)} className="os-input">
              <option>HIGH</option><option>NORMAL</option><option>LOW</option>
            </select>
          </div>
          <div>
            <label className="os-label block mb-1.5">PAYLOAD <span style={{ color: "#384858", textTransform: "none", letterSpacing: 0, fontSize: 10 }}>(JSON)</span></label>
            <textarea value={payload} onChange={(e) => { setPayload(e.target.value); setErr(""); }} rows={4}
              className={`os-input font-mono text-[12px] resize-none ${err ? "border-red-500" : ""}`} />
            {err && <p style={{ fontSize: 11, color: "#C06070", marginTop: 4 }}>{err}</p>}
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="btn btn-ghost">cancel</button>
            <button type="submit" disabled={isPending || !title.trim()} className="btn btn-primary"
              style={{ opacity: isPending || !title.trim() ? 0.4 : 1 }}>
              {isPending && <Loader2 className="w-3 h-3 animate-spin" />}
              Spawn
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ── Main ────────────────────────────────────────────────── */
export default function RuntimeDashboard() {
  const uptime = useUptime();
  const [showModal, setShowModal] = useState(false);
  const { data: jobs = [] } = useJobs();
  const { data: agents = [] } = useAgents();
  const { data: metrics } = useMetrics();
  const { data: events = [] } = useEvents({ limit: 30 });

  const byStatus = (s: JobStatus) => jobs.filter((j) => j.status === s).length;
  const running = byStatus("RUNNING");
  const planning = byStatus("PLANNING");
  const completed = byStatus("COMPLETED");
  const failed = byStatus("FAILED");
  const activeAgents = agents.filter((a) => a.is_active).length;
  const successRate = jobs.length > 0
    ? ((completed / jobs.length) * 100).toFixed(1)
    : "—";

  return (
    <div className="flex flex-col h-full">
      {showModal && <QuickJobModal onClose={() => setShowModal(false)} />}

      {/* Page topbar */}
      <div className="page-topbar">
        <div>
          <div className="page-title">Dashboard</div>
          <div className="page-sub">
            <span className="dot dot-running" style={{ width: 6, height: 6, display: "inline-flex", marginRight: 5, verticalAlign: "middle" }} />
            <span className="text-green" style={{ fontWeight: 500, fontSize: 11 }}>OPERATIONAL</span>
            <span style={{ margin: "0 8px", color: "#2A3848" }}>·</span>
            uptime <strong style={{ color: "#607080", fontWeight: 500 }}>{uptime}</strong>
            <span style={{ margin: "0 8px", color: "#2A3848" }}>·</span>
            {activeAgents} agents registered
            {metrics && (
              <>
                <span style={{ margin: "0 8px", color: "#2A3848" }}>·</span>
                <span className="text-green" style={{ fontWeight: 500 }}>{(metrics.success_rate_7d * 100).toFixed(1)}%</span> success / 7d
              </>
            )}
          </div>
        </div>
        <button onClick={() => setShowModal(true)} className="btn btn-primary">
          <Plus style={{ width: 14, height: 14 }} />
          Spawn
        </button>
      </div>

      <div className="page-content space-y-5">

        {/* ── Stat cards ─────────────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
          <div className="stat-card">
            <div className="stat-label">Running</div>
            <div className="stat-value" style={{ color: running > 0 ? "#60A890" : undefined }}>{running}</div>
            <div className="stat-sub">{planning} planning</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Pending</div>
            <div className="stat-value">{byStatus("PENDING")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Completed</div>
            <div className="stat-value">{completed}</div>
            <div className="stat-sub up">
              {metrics ? `${metrics.jobs_completed_last_24h} today` : ""}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Failed</div>
            <div className="stat-value" style={{ color: failed > 0 ? "#C06070" : undefined }}>{failed}</div>
            <div className={`stat-sub ${failed > 0 ? "down" : ""}`}>
              {metrics ? `${metrics.jobs_failed_last_24h} today` : ""}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Success Rate</div>
            <div className="stat-value" style={{ fontSize: 22 }}>{successRate}<span style={{ fontSize: 14, fontWeight: 400, color: "#607080" }}>{jobs.length > 0 ? "%" : ""}</span></div>
            <div className="stat-sub">7d avg {metrics ? `${(metrics.success_rate_7d * 100).toFixed(0)}%` : "—"}</div>
          </div>
        </div>

        {/* ── Main two-column ──────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16 }}>

          {/* Active processes */}
          <div className="os-card overflow-hidden">
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "12px 18px", borderBottom: "1px solid hsl(var(--border))",
            }}>
              <span className="os-label">ACTIVE PROCESSES</span>
              <Link href="/jobs" style={{ fontSize: 11, color: "#607080", display: "flex", alignItems: "center", gap: 2, textDecoration: "none" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "#C8A040")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "#607080")}
              >
                all <ChevronRight style={{ width: 12, height: 12 }} />
              </Link>
            </div>

            {/* Column headers */}
            <div style={{
              display: "grid", gridTemplateColumns: "80px 1fr 120px 64px 72px",
              gap: 8, padding: "8px 18px",
              fontSize: 9, letterSpacing: "0.1em", color: "#384858",
              textTransform: "uppercase", borderBottom: "1px solid hsl(var(--border))",
              userSelect: "none",
            }}>
              <span>PID</span><span>Title</span><span>Status</span><span>Tokens</span><span>Age</span>
            </div>

            <div>
              {jobs
                .filter((j) => j.status === "RUNNING" || j.status === "PLANNING" || j.status === "PENDING")
                .slice(0, 8)
                .map((job) => (
                  <Link
                    key={job.id}
                    href={`/jobs/${job.id}`}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "80px 1fr 120px 64px 72px",
                      gap: 8, padding: "10px 18px",
                      borderBottom: "1px solid hsl(var(--border) / 0.5)",
                      alignItems: "center",
                      textDecoration: "none",
                      transition: "background 0.1s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#182028")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <span className="pid">{job.id.slice(0, 8)}</span>
                    <span style={{ fontSize: 12.5, color: "#D8E0E8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {job.title}
                    </span>
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className={`dot dot-${job.status.toLowerCase()}`} />
                      <span style={{
                        fontSize: 11,
                        color: job.status === "RUNNING" ? "#60A890" : job.status === "PLANNING" ? "#5090A8" : "#C8A040",
                      }}>{job.status}</span>
                    </span>
                    <span style={{ fontSize: 11, color: "#607080", fontVariantNumeric: "tabular-nums" }}>{formatTokens(job.total_tokens)}</span>
                    <span style={{ fontSize: 11, color: "#607080" }}>{formatRelative(job.created_at)}</span>
                  </Link>
                ))}
              {jobs.filter((j) => ["RUNNING", "PLANNING", "PENDING"].includes(j.status)).length === 0 && (
                <div style={{ padding: "32px 0", textAlign: "center", fontSize: 12, color: "#384858" }}>
                  no active processes
                </div>
              )}
            </div>
          </div>

          {/* System resources */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="os-card overflow-hidden">
              <div style={{ padding: "12px 16px", borderBottom: "1px solid hsl(var(--border))" }}>
                <span className="os-label">SYSTEM RESOURCES</span>
              </div>
              <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 14 }}>

                {/* Agent pool */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 11, color: "#607080" }}>Agent Pool</span>
                    <span style={{ fontSize: 11, color: "#D8E0E8", fontVariantNumeric: "tabular-nums" }}>{activeAgents} registered</span>
                  </div>
                  <div style={{ display: "flex", gap: 3 }}>
                    {Array.from({ length: Math.min(activeAgents, 12) }).map((_, i) => (
                      <span key={i} className="dot dot-green" style={{ width: 7, height: 7 }} />
                    ))}
                  </div>
                </div>

                <div style={{ borderTop: "1px solid hsl(var(--border) / 0.5)" }} />

                {/* Completed today */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                    <span style={{ fontSize: 11, color: "#607080" }}>Completed / 24h</span>
                    <span className="text-green" style={{ fontSize: 11, fontVariantNumeric: "tabular-nums" }}>{metrics?.jobs_completed_last_24h ?? 0}</span>
                  </div>
                  <Gauge pct={metrics ? Math.min(metrics.jobs_completed_last_24h * 5, 100) : 0} color="gauge-green" />
                </div>

                {/* Failed today */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                    <span style={{ fontSize: 11, color: "#607080" }}>Failed / 24h</span>
                    <span className="text-red" style={{ fontSize: 11, fontVariantNumeric: "tabular-nums" }}>{metrics?.jobs_failed_last_24h ?? 0}</span>
                  </div>
                  <Gauge pct={metrics ? Math.min(metrics.jobs_failed_last_24h * 10, 100) : 0} color="gauge-red" />
                </div>

                {/* Cost today */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                    <span style={{ fontSize: 11, color: "#607080" }}>Cost / Today</span>
                    <span className="text-amber" style={{ fontSize: 11, fontVariantNumeric: "tabular-nums" }}>{formatCost(metrics?.total_cost_today)}</span>
                  </div>
                  <Gauge pct={metrics ? Math.min((metrics.total_cost_today ?? 0) * 100, 100) : 0} color="gauge-amber" />
                </div>

                {/* Tokens today */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                    <span style={{ fontSize: 11, color: "#607080" }}>Tokens / Today</span>
                    <span style={{ fontSize: 11, color: "#C8A040", fontVariantNumeric: "tabular-nums" }}>{formatTokens(metrics?.total_tokens_today)}</span>
                  </div>
                  <Gauge pct={metrics ? Math.min((metrics.total_tokens_today ?? 0) / 1000, 100) : 0} color="gauge-cyan" />
                </div>
              </div>
            </div>

            {/* Queue depth mini-chart */}
            <div className="os-card" style={{ padding: "12px 16px" }}>
              <div className="os-label" style={{ marginBottom: 10 }}>QUEUE DEPTH</div>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 36 }}>
                {(["PENDING","PLANNING","RUNNING","COMPLETED","FAILED"] as JobStatus[]).map((s) => {
                  const n = byStatus(s);
                  const maxH = Math.max(...(["PENDING","PLANNING","RUNNING","COMPLETED","FAILED"] as JobStatus[]).map(byStatus), 1);
                  const h = n === 0 ? 2 : Math.max((n / maxH) * 36, 4);
                  const colors: Record<string, string> = {
                    PENDING: "#5090A8", PLANNING: "#C8A040", RUNNING: "#60A890", COMPLETED: "#3A6070", FAILED: "#C06070",
                  };
                  return (
                    <div key={s} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, flex: 1 }}>
                      <div style={{
                        height: h, background: colors[s] ?? "#2A3848",
                        width: "100%", borderRadius: 2, transition: "height 0.5s ease",
                      }} />
                      <span style={{ fontSize: 8, color: "#384858" }}>{n}</span>
                    </div>
                  );
                })}
              </div>
              <div style={{ display: "flex", marginTop: 2 }}>
                {["PND", "PLN", "RUN", "DONE", "FAIL"].map((l) => (
                  <span key={l} style={{ flex: 1, textAlign: "center", fontSize: 8, color: "#384858" }}>{l}</span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── Event stream ──────────────────────────────────── */}
        <div className="os-card overflow-hidden">
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "12px 18px", borderBottom: "1px solid hsl(var(--border))",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="dot dot-running" style={{ width: 6, height: 6 }} />
              <span className="os-label">LIVE EVENT STREAM</span>
            </div>
            <Link href="/events" style={{ fontSize: 11, color: "#607080", display: "flex", alignItems: "center", gap: 2, textDecoration: "none" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#C8A040")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#607080")}
            >
              full log <ChevronRight style={{ width: 12, height: 12 }} />
            </Link>
          </div>
          <div style={{ height: 160, overflowY: "auto" }}>
            {events.length === 0 ? (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 12, color: "#384858" }}>
                no events yet — spawn a process to begin
              </div>
            ) : (
              events.slice(0, 20).map((ev) => {
                const ts = new Date(ev.timestamp);
                const timeStr = `${String(ts.getHours()).padStart(2,"0")}:${String(ts.getMinutes()).padStart(2,"0")}:${String(ts.getSeconds()).padStart(2,"0")}`;
                return (
                  <div key={ev.id} className="event-row-enter" style={{
                    display: "flex", alignItems: "center", gap: 12,
                    padding: "6px 18px",
                    borderBottom: "1px solid hsl(var(--border) / 0.3)",
                    fontSize: 11,
                  }}>
                    <span style={{ color: "#384858", fontVariantNumeric: "tabular-nums", flexShrink: 0, width: 60 }}>{timeStr}</span>
                    <span className="pid" style={{ flexShrink: 0, width: 64 }}>
                      {ev.job_id ? ev.job_id.slice(0, 8) : "sys"}
                    </span>
                    <span className={`${EVENT_COLOR[ev.event_type] ?? "text-muted-foreground"}`} style={{ fontWeight: 500, flexShrink: 0, width: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {ev.event_type}
                    </span>
                    <span style={{ color: "#607080", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {ev.agent_instance_id ? `agent:${ev.agent_instance_id.slice(0, 8)}` : ""}
                      {ev.payload?.tool_name ? ` · ${ev.payload.tool_name}` : ""}
                      {ev.payload?.error ? ` · ${String(ev.payload.error).slice(0, 50)}` : ""}
                    </span>
                    {ev.duration_ms && (
                      <span style={{ marginLeft: "auto", color: "#384858", fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>{ev.duration_ms}ms</span>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
