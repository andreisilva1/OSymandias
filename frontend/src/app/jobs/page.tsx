"use client";

import Link from "next/link";
import { useState, useMemo } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { useJobs } from "@/hooks/useJobData";
import { formatRelative, formatCost, formatTokens } from "@/lib/utils";
import { Plus, Loader2, ChevronRight, ChevronLeft, Search } from "lucide-react";
import { api } from "@/lib/api";
import type { JobStatus } from "@/types";

const PAGE_SIZE = 15;

const STATUS_FILTERS = ["ALL", "RUNNING", "PLANNING", "PENDING", "COMPLETED", "FAILED", "CANCELLED", "BUDGET_EXCEEDED"] as const;
type Filter = (typeof STATUS_FILTERS)[number];

const CARD_CLASS: Record<string, string> = {
  RUNNING: "job-card-running", PLANNING: "job-card-planning",
  COMPLETED: "job-card-completed", FAILED: "job-card-failed",
  PENDING: "job-card-pending", BUDGET_EXCEEDED: "job-card-failed",
};
const DOT_CLASS: Record<string, string> = {
  RUNNING: "dot-running", PLANNING: "dot-planning", PENDING: "dot-pending",
  WAITING: "dot-waiting", FAILED: "dot-failed", CRASHED: "dot-failed",
  COMPLETED: "dot-completed", CANCELLED: "dot-cancelled", BUDGET_EXCEEDED: "dot-failed",
};
const BADGE_CLASS: Record<string, string> = {
  RUNNING: "badge-running", PLANNING: "badge-planning", COMPLETED: "badge-completed",
  FAILED: "badge-failed", PENDING: "badge-pending", CANCELLED: "badge-cancelled",
  BUDGET_EXCEEDED: "badge-failed",
};

function NewProcessModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("NORMAL");
  const [maxTokens, setMaxTokens] = useState("");
  const [payload, setPayload] = useState("{}");
  const [err, setErr] = useState("");

  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      api.jobs.create({
        title, description: description || undefined, priority,
        input_payload: JSON.parse(payload),
        max_tokens: maxTokens.trim() ? Number(maxTokens) : null,
      }),
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
            <label className="os-label block mb-1.5">MAX TOKENS <span style={{ color: "#384858", textTransform: "none", letterSpacing: 0, fontSize: 10 }}>(budget cap — optional)</span></label>
            <input type="number" min={0} value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)}
              className="os-input" placeholder="e.g. 50000 — halts the job if exceeded" />
          </div>
          <div>
            <label className="os-label block mb-1.5">PAYLOAD <span style={{ color: "#384858", textTransform: "none", letterSpacing: 0, fontSize: 10 }}>(JSON)</span></label>
            <textarea value={payload} onChange={(e) => { setPayload(e.target.value); setErr(""); }} rows={4}
              className={`os-input font-mono text-[12px] resize-none ${err ? "border-red-500" : ""}`} />
            {err && <p style={{ fontSize: 11, color: "#C06070", marginTop: 4 }}>{err}</p>}
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="btn btn-ghost">cancel</button>
            <button type="submit" disabled={isPending || !title.trim()} className="btn btn-primary" style={{ opacity: isPending || !title.trim() ? 0.4 : 1 }}>
              {isPending && <Loader2 className="w-3 h-3 animate-spin" />}
              Spawn
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function ProcessesPage() {
  const [filter, setFilter] = useState<Filter>("ALL");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [showModal, setShowModal] = useState(false);
  const { data: allJobs = [], isLoading } = useJobs();

  const byStatus = (s: string) => allJobs.filter((j) => j.status === s).length;

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allJobs.filter((j) => {
      if (filter !== "ALL" && j.status !== filter) return false;
      if (q && !j.title.toLowerCase().includes(q) && !(j.description ?? "").toLowerCase().includes(q)) return false;
      return true;
    });
  }, [allJobs, filter, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const jobs = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  function changeFilter(f: Filter) { setFilter(f); setPage(1); }
  function changeSearch(v: string) { setSearch(v); setPage(1); }

  const running = byStatus("RUNNING") + byStatus("PLANNING");
  const successRate = allJobs.length > 0
    ? Math.round((byStatus("COMPLETED") / allJobs.length) * 100)
    : 0;

  return (
    <div className="flex flex-col h-full">
      {showModal && <NewProcessModal onClose={() => setShowModal(false)} />}

      {/* Topbar */}
      <div className="page-topbar">
        <div>
          <div className="page-title">Processes</div>
          <div className="page-sub">Kernel process manager · {allJobs.length} total</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: "#607080" }} />}
          <button onClick={() => setShowModal(true)} className="btn btn-primary">
            <Plus style={{ width: 14, height: 14 }} />
            Spawn
          </button>
        </div>
      </div>

      <div className="page-content">

        {/* Stat row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
          <div className="stat-card">
            <div className="stat-label">Total Processes</div>
            <div className="stat-value">{allJobs.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Active</div>
            <div className="stat-value" style={{ color: running > 0 ? "#60A890" : undefined }}>{running}</div>
            <div className="stat-sub">{byStatus("RUNNING")} running · {byStatus("PLANNING")} planning</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Completed</div>
            <div className="stat-value">{byStatus("COMPLETED")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Success Rate</div>
            <div className="stat-value">{successRate}<span style={{ fontSize: 16, fontWeight: 400, color: "#607080" }}>%</span></div>
            <div className={`stat-sub ${byStatus("FAILED") === 0 ? "" : "down"}`}>
              {byStatus("FAILED")} failed
            </div>
          </div>
        </div>

        {/* Filter bar */}
        <div className="filter-bar">
          <div className="search-wrap">
            <Search style={{ width: 13, height: 13 }} />
            <input
              className="search-bar"
              value={search}
              onChange={(e) => changeSearch(e.target.value)}
              placeholder="Search by title or description..."
            />
          </div>
          <select
            className="filter-select"
            value={filter}
            onChange={(e) => changeFilter(e.target.value as Filter)}
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f} value={f}>
                {f === "ALL" ? `All (${allJobs.length})` : `${f} (${byStatus(f)})`}
              </option>
            ))}
          </select>
        </div>

        {/* Job list */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {jobs.map((job) => (
            <Link
              key={job.id}
              href={`/jobs/${job.id}`}
              className={`job-card ${CARD_CLASS[job.status] ?? ""}`}
            >
              {/* Left: title + meta */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13.5, fontWeight: 500, color: "#D8E0E8", marginBottom: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {job.title}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span className="pid">{job.id.slice(0, 8)}</span>
                  {job.description && (
                    <span style={{ fontSize: 11, color: "#607080", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 280 }}>
                      {job.description}
                    </span>
                  )}
                </div>
              </div>

              {/* Right: meta */}
              <div style={{ display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
                {job.priority === "HIGH" && (
                  <span style={{ fontSize: 10, fontWeight: 600, color: "#C8A040", letterSpacing: "0.05em" }}>HIGH</span>
                )}
                <span style={{ fontSize: 11, color: "#607080", fontVariantNumeric: "tabular-nums" }}>
                  {formatTokens(job.total_tokens)}
                </span>
                <span style={{ fontSize: 11, color: "#607080", fontVariantNumeric: "tabular-nums" }}>
                  {formatCost(job.estimated_cost)}
                </span>
                <span style={{ fontSize: 11, color: "#607080" }}>
                  {formatRelative(job.created_at)}
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span className={`dot ${DOT_CLASS[job.status] ?? "dot-dim"}`} />
                  <span className={`status-badge ${BADGE_CLASS[job.status] ?? ""}`}>
                    {job.status}
                  </span>
                </div>
                <ChevronRight style={{ width: 14, height: 14, color: "#384858" }} />
              </div>
            </Link>
          ))}

          {jobs.length === 0 && !isLoading && (
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              padding: "48px 0", fontSize: 13, color: "#607080",
            }}>
              No processes match the current filter.
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="pagination">
            <span className="page-info">
              Showing {(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, filtered.length)} of {filtered.length}
            </span>
            <div className="page-btns">
              <button
                className="page-btn"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage === 1}
              >
                <ChevronLeft style={{ width: 13, height: 13 }} />
              </button>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  className={`page-btn ${p === safePage ? "active" : ""}`}
                  onClick={() => setPage(p)}
                >
                  {p}
                </button>
              ))}
              <button
                className="page-btn"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage === totalPages}
              >
                <ChevronRight style={{ width: 13, height: 13 }} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
