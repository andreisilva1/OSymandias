"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useJobs, useAgents, useMetrics, useEvents } from "@/hooks/useJobData";
import { formatTokens, formatCost, formatRelative } from "@/lib/utils";
import { ChevronRight, Plus } from "lucide-react";
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
    <div className="gauge flex-1" style={{ height: 4 }}>
      <div className={`gauge-fill ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

/* ── Queue stat card ────────────────────────────────────── */
function QStat({
  label, count, dotClass, href,
}: { label: string; count: number; dotClass: string; href?: string }) {
  const inner = (
    <div className="border border-border bg-card px-3 py-3 hover:bg-accent transition-colors cursor-default rounded-[var(--radius)]">
      <div className="flex items-center gap-1.5 mb-2">
        <span className={`dot ${dotClass}`} />
        <span className="os-label">{label}</span>
      </div>
      <div className="text-[24px] font-semibold tabular text-bright leading-none">{count}</div>
    </div>
  );
  return href ? <Link href={`/jobs?status=${label}`}>{inner}</Link> : inner;
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
      api.jobs.create({
        title,
        description: description || undefined,
        priority,
        input_payload: JSON.parse(payload),
      }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["jobs"] }); onClose(); },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("");
    try { JSON.parse(payload); } catch { setErr("Invalid JSON in payload"); return; }
    mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div className="bg-card border border-border p-6 w-[460px] rounded-[6px] shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="os-label mb-5">SPAWN PROCESS</div>
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
            <label className="os-label block mb-1.5">INPUT PAYLOAD <span className="text-muted-foreground/30 normal-case tracking-normal">(JSON)</span></label>
            <textarea value={payload} onChange={(e) => { setPayload(e.target.value); setErr(""); }} rows={4}
              className={`os-input font-mono text-[12px] resize-none ${err ? "border-red-500" : ""}`} />
            {err && <p className="text-[11px] text-red mt-1">{err}</p>}
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="px-4 py-2 text-[12px] text-muted-foreground border border-border rounded-[var(--radius)] hover:bg-accent transition-colors">
              ESC / cancel
            </button>
            <button type="submit" disabled={isPending || !title.trim()}
              className="flex items-center gap-1.5 px-4 py-2 text-[12px] rounded-[var(--radius)] border disabled:opacity-40 transition-colors"
              style={{ background: "rgba(201,168,76,0.08)", borderColor: "#C9A84C", color: "#C9A84C" }}>
              {isPending ? "Spawning…" : "SPAWN"}
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
  const pending = byStatus("PENDING");
  const completed = byStatus("COMPLETED");
  const failed = byStatus("FAILED");
  const activeAgents = agents.filter((a) => a.is_active).length;
  const now = Date.now();

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {showModal && <QuickJobModal onClose={() => setShowModal(false)} />}

      {/* ── System status bar ──────────────────────────────── */}
      <div
        className="flex items-center gap-6 px-5 py-2 border-b border-border text-[10px] text-muted-foreground shrink-0"
        style={{ background: "#0A0908" }}
      >
        <span className="flex items-center gap-1.5">
          <span className="dot dot-running" style={{ width: 5, height: 5 }} />
          <span className="text-green font-medium">OPERATIONAL</span>
        </span>
        <span className="text-border">│</span>
        <span>uptime <span className="text-foreground tabular">{uptime}</span></span>
        <span className="text-border">│</span>
        <span>procs <span className="text-foreground tabular">{jobs.length}</span></span>
        <span className="text-border">│</span>
        <span>agents <span className="text-foreground tabular">{activeAgents}</span> registered</span>
        <span className="text-border">│</span>
        <span>success_rate_7d <span className="text-green tabular">{metrics ? `${(metrics.success_rate_7d * 100).toFixed(1)}%` : "—"}</span></span>
        <div className="flex-1" />
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-1 px-2 py-1 border border-border hover:border-[#C9A84C] hover:text-[#C9A84C] transition-colors"
        >
          <Plus className="w-3 h-3" />
          <span>spawn</span>
        </button>
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-4">

        {/* ── Process queue ──────────────────────────────────── */}
        <div>
          <div className="os-label mb-2">PROCESS QUEUE</div>
          <div className="grid grid-cols-5 gap-2">
            <QStat label="RUNNING"   count={running}   dotClass="dot-running"   href="/jobs" />
            <QStat label="PLANNING"  count={planning}  dotClass="dot-planning"  href="/jobs" />
            <QStat label="PENDING"   count={pending}   dotClass="dot-pending"   href="/jobs" />
            <QStat label="COMPLETED" count={completed} dotClass="dot-completed" href="/jobs" />
            <QStat label="FAILED"    count={failed}    dotClass="dot-failed"    href="/jobs" />
          </div>
        </div>

        {/* ── Main two-column ──────────────────────────────── */}
        <div className="grid grid-cols-5 gap-4">

          {/* Active processes */}
          <div className="col-span-3 border border-border bg-card rounded-[var(--radius)] overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 border-b border-border">
              <span className="os-label">ACTIVE PROCESSES</span>
              <Link href="/jobs" className="text-[10px] text-muted-foreground hover:text-[#C9A84C] flex items-center gap-0.5">
                all <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="divide-y divide-border">
              {/* header */}
              <div className="grid grid-cols-[80px_1fr_100px_60px_70px] gap-2 px-4 py-1.5 text-[9px] tracking-[0.1em] text-muted-foreground/30 uppercase select-none">
                <span>PID</span><span>TITLE</span><span>STATUS</span><span>TOKENS</span><span>AGE</span>
              </div>
              {jobs
                .filter((j) => j.status === "RUNNING" || j.status === "PLANNING" || j.status === "PENDING")
                .slice(0, 8)
                .map((job) => (
                  <Link
                    key={job.id}
                    href={`/jobs/${job.id}`}
                    className="grid grid-cols-[80px_1fr_100px_60px_70px] gap-2 px-4 py-2 hover:bg-accent transition-colors items-center"
                  >
                    <span className="text-[10px] text-muted-foreground tabular font-mono">{job.id.slice(0, 8)}</span>
                    <span className="text-[11px] text-foreground truncate">{job.title}</span>
                    <span className="flex items-center gap-1.5">
                      <span className={`dot dot-${job.status.toLowerCase()}`} />
                      <span className={`text-[10px] ${job.status === "RUNNING" ? "text-green" : job.status === "PLANNING" ? "text-cyan" : "text-amber"}`}>
                        {job.status}
                      </span>
                    </span>
                    <span className="text-[10px] text-muted-foreground tabular">{formatTokens(job.total_tokens)}</span>
                    <span className="text-[10px] text-muted-foreground tabular">{formatRelative(job.created_at)}</span>
                  </Link>
                ))}
              {jobs.filter((j) => ["RUNNING", "PLANNING", "PENDING"].includes(j.status)).length === 0 && (
                <div className="px-4 py-6 text-center text-[11px] text-muted-foreground/40">
                  no active processes
                </div>
              )}
            </div>
          </div>

          {/* System resources */}
          <div className="col-span-2 space-y-2">
            <div className="border border-border bg-card rounded-[var(--radius)] overflow-hidden">
              <div className="px-4 py-2.5 border-b border-border">
                <span className="os-label">SYSTEM RESOURCES</span>
              </div>
              <div className="px-4 py-3 space-y-3">

                {/* Agent pool */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] text-muted-foreground">AGENT POOL</span>
                    <span className="text-[10px] tabular text-foreground">{activeAgents} registered</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex gap-0.5">
                      {Array.from({ length: Math.min(activeAgents, 10) }).map((_, i) => (
                        <span key={i} className="dot dot-green" style={{ width: 8, height: 8 }} />
                      ))}
                    </div>
                  </div>
                </div>

                <div className="border-t border-border/50" />

                {/* Jobs today */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-muted-foreground">COMPLETED / 24H</span>
                    <span className="text-[10px] tabular text-green">{metrics?.jobs_completed_last_24h ?? 0}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Gauge pct={metrics ? Math.min(metrics.jobs_completed_last_24h * 5, 100) : 0} color="gauge-green" />
                  </div>
                </div>

                {/* Failed today */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-muted-foreground">FAILED / 24H</span>
                    <span className="text-[10px] tabular text-red">{metrics?.jobs_failed_last_24h ?? 0}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Gauge pct={metrics ? Math.min(metrics.jobs_failed_last_24h * 10, 100) : 0} color="gauge-red" />
                  </div>
                </div>

                {/* Cost today */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-muted-foreground">COST / TODAY</span>
                    <span className="text-[10px] tabular text-amber">{formatCost(metrics?.total_cost_today)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Gauge pct={metrics ? Math.min((metrics.total_cost_today ?? 0) * 100, 100) : 0} color="gauge-amber" />
                  </div>
                </div>

                {/* Tokens today */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-muted-foreground">TOKENS / TODAY</span>
                    <span className="text-[10px] tabular text-cyan" style={{ color: "#C9A84C" }}>{formatTokens(metrics?.total_tokens_today)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Gauge pct={metrics ? Math.min((metrics.total_tokens_today ?? 0) / 1000, 100) : 0} color="gauge-cyan" />
                  </div>
                </div>
              </div>
            </div>

            {/* Queue depth */}
            <div className="border border-border bg-card px-4 py-3 rounded-[var(--radius)]">
              <div className="os-label mb-2">QUEUE DEPTH</div>
              <div className="flex items-end gap-1 h-8">
                {(["PENDING","PLANNING","RUNNING","COMPLETED","FAILED"] as JobStatus[]).map((s) => {
                  const n = byStatus(s);
                  const maxH = Math.max(...(["PENDING","PLANNING","RUNNING","COMPLETED","FAILED"] as JobStatus[]).map(byStatus), 1);
                  const h = n === 0 ? 2 : Math.max((n / maxH) * 32, 4);
                  const colors: Record<string, string> = {
                    PENDING:"#f59e0b", PLANNING:"#7BAABF", RUNNING:"#8FB5A0", COMPLETED:"#2a3f52", FAILED:"#ef4444",
                  };
                  return (
                    <div key={s} className="flex flex-col items-center gap-1 flex-1">
                      <div style={{ height: h, background: colors[s], width: "100%", transition: "height 0.5s ease" }} />
                      <span className="text-[8px] text-muted-foreground/40">{n}</span>
                    </div>
                  );
                })}
              </div>
              <div className="flex text-[8px] text-muted-foreground/30 mt-1">
                {["PND","PLN","RUN","DONE","FAIL"].map((l) => (
                  <span key={l} className="flex-1 text-center">{l}</span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── Event stream ──────────────────────────────────── */}
        <div className="border border-border bg-card rounded-[var(--radius)] overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
            <div className="flex items-center gap-2">
              <span className="dot dot-running" style={{ width: 5, height: 5 }} />
              <span className="os-label">LIVE EVENT STREAM</span>
            </div>
            <Link href="/events" className="text-[10px] text-muted-foreground hover:text-[#C9A84C] flex items-center gap-0.5">
              full log <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="h-40 overflow-y-auto">
            {events.length === 0 ? (
              <div className="flex items-center justify-center h-full text-[11px] text-muted-foreground/30">
                no events yet — spawn a process to begin
              </div>
            ) : (
              events.slice(0, 20).map((ev) => {
                const ts = new Date(ev.timestamp);
                const timeStr = `${String(ts.getHours()).padStart(2,"0")}:${String(ts.getMinutes()).padStart(2,"0")}:${String(ts.getSeconds()).padStart(2,"0")}.${String(ts.getMilliseconds()).padStart(3,"0")}`;
                const evColor = EVENT_COLOR[ev.event_type] ?? "text-muted-foreground";
                return (
                  <div key={ev.id} className="flex items-center gap-3 px-4 py-1 hover:bg-accent/40 border-b border-border/30 event-row-enter">
                    <span className="text-[10px] text-muted-foreground/40 tabular shrink-0 w-28">{timeStr}</span>
                    <span className="text-[10px] text-muted-foreground tabular shrink-0 w-24 truncate">
                      {ev.job_id ? ev.job_id.slice(0, 8) : "sys"}
                    </span>
                    <span className={`text-[10px] font-medium shrink-0 w-36 truncate ${evColor}`}>{ev.event_type}</span>
                    <span className="text-[10px] text-muted-foreground/60 truncate">
                      {ev.agent_instance_id ? `agent:${ev.agent_instance_id.slice(0, 8)}` : ""}
                      {ev.payload?.tool_name ? ` · ${ev.payload.tool_name}` : ""}
                      {ev.payload?.error ? ` · ${String(ev.payload.error).slice(0, 40)}` : ""}
                    </span>
                    {ev.duration_ms && (
                      <span className="ml-auto text-[10px] text-muted-foreground/30 tabular shrink-0">{ev.duration_ms}ms</span>
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
