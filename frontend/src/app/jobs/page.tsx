"use client";

import Link from "next/link";
import { useState, useMemo } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { useJobs } from "@/hooks/useJobData";
import { formatRelative, formatCost, formatTokens } from "@/lib/utils";
import { Plus, Loader2, ChevronRight, Search, ChevronLeft } from "lucide-react";
import { api } from "@/lib/api";
import type { JobStatus } from "@/types";

type Filter = JobStatus | "ALL";
const FILTERS: Filter[] = ["ALL", "RUNNING", "PLANNING", "PENDING", "COMPLETED", "FAILED", "CANCELLED"];
const PAGE_SIZE = 15;

const DOT: Record<string, string> = {
  RUNNING:"dot-running", PLANNING:"dot-planning", PENDING:"dot-pending",
  WAITING:"dot-waiting", FAILED:"dot-failed", CRASHED:"dot-failed",
  COMPLETED:"dot-completed", CANCELLED:"dot-cancelled",
};
const COL: Record<string, string> = {
  RUNNING:"text-green", PLANNING:"text-cyan", PENDING:"text-amber",
  FAILED:"text-red", COMPLETED:"text-muted-foreground", CANCELLED:"text-muted-foreground",
};

function NewProcessModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("NORMAL");
  const [payload, setPayload] = useState("{}");
  const [err, setErr] = useState("");

  const { mutate, isPending } = useMutation({
    mutationFn: () => api.jobs.create({ title, description: description || undefined, priority, input_payload: JSON.parse(payload) }),
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
              style={{ background:"rgba(201,168,76,0.08)", borderColor:"#C9A84C", color:"#C9A84C" }}>
              {isPending && <Loader2 className="w-3 h-3 animate-spin" />}
              SPAWN
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

  return (
    <div className="flex flex-col h-full">
      {showModal && <NewProcessModal onClose={() => setShowModal(false)} />}

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border shrink-0">
        <div>
          <div className="os-label mb-0.5">KERNEL / PROCESS MANAGER</div>
          <h1 className="text-[15px] font-semibold text-bright">Processes</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[12px] text-muted-foreground tabular">{filtered.length} / {allJobs.length}</span>
          <button onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] border border-border rounded-[var(--radius)] hover:border-[#C9A84C] hover:text-[#C9A84C] transition-colors">
            <Plus className="w-3.5 h-3.5" /> SPAWN
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-px px-5 py-2 border-b border-border shrink-0 bg-card/50">
        {FILTERS.map((f) => {
          const count = f === "ALL" ? allJobs.length : allJobs.filter((j) => j.status === f).length;
          return (
            <button key={f} onClick={() => changeFilter(f)}
              className={`px-3 py-1.5 text-[11px] transition-colors tracking-wide rounded-sm ${
                filter === f
                  ? "text-foreground bg-accent border-b-2 border-[#C9A84C]"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/40"
              }`}>
              {f} <span className="ml-1 opacity-40 tabular">{count}</span>
            </button>
          );
        })}
        {isLoading && <Loader2 className="w-3 h-3 animate-spin text-muted-foreground ml-2" />}
        <div className="ml-auto flex items-center gap-1.5 border border-border rounded-[var(--radius)] px-2.5 py-1 bg-background">
          <Search className="w-3 h-3 text-muted-foreground/40 shrink-0" />
          <input
            value={search}
            onChange={(e) => changeSearch(e.target.value)}
            placeholder="search..."
            className="bg-transparent text-[11px] text-foreground placeholder:text-muted-foreground/30 outline-none w-36"
          />
        </div>
      </div>

      {/* Process table */}
      <div className="flex-1 overflow-auto">
        {/* Column headers */}
        <div className="grid grid-cols-[88px_1fr_110px_80px_70px_70px_80px_28px] gap-2 px-5 py-2 text-[9px] tracking-[0.1em] text-muted-foreground/30 uppercase border-b border-border sticky top-0 bg-background/95 backdrop-blur select-none">
          <span>PID</span>
          <span>TITLE</span>
          <span>STATUS</span>
          <span>PRIORITY</span>
          <span>TOKENS</span>
          <span>COST</span>
          <span>AGE</span>
          <span />
        </div>

        <div className="divide-y divide-border/50">
          {jobs.map((job) => (
            <Link key={job.id} href={`/jobs/${job.id}`}
              className="grid grid-cols-[88px_1fr_110px_80px_70px_70px_80px_28px] gap-2 px-5 py-3 hover:bg-accent/60 transition-colors items-center group">
              <span className="pid">{job.id.slice(0, 8)}</span>
              <div className="min-w-0">
                <div className="text-[13px] text-foreground truncate">{job.title}</div>
                {job.description && <div className="text-[11px] text-muted-foreground/50 truncate mt-0.5">{job.description}</div>}
              </div>
              <span className="flex items-center gap-1.5">
                <span className={`dot ${DOT[job.status] ?? "dot-dim"}`} />
                <span className={`text-[11px] ${COL[job.status] ?? "text-muted-foreground"}`}>{job.status}</span>
              </span>
              <span className={`text-[11px] tabular ${job.priority === "HIGH" ? "text-amber" : "text-muted-foreground"}`}>
                {job.priority}
              </span>
              <span className="text-[11px] text-muted-foreground tabular font-mono">{formatTokens(job.total_tokens)}</span>
              <span className="text-[11px] text-muted-foreground tabular font-mono">{formatCost(job.estimated_cost)}</span>
              <span className="text-[11px] text-muted-foreground tabular">{formatRelative(job.created_at)}</span>
              <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/30 group-hover:text-muted-foreground transition-colors" />
            </Link>
          ))}
          {jobs.length === 0 && !isLoading && (
            <div className="flex items-center justify-center py-16 text-[12px] text-muted-foreground/30">
              no processes match filter
            </div>
          )}
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-5 py-2.5 border-t border-border shrink-0 bg-card/50">
          <span className="text-[11px] text-muted-foreground/40 tabular">
            {(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, filtered.length)} of {filtered.length}
          </span>
          <div className="flex items-center gap-1">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={safePage === 1}
              className="p-1 rounded-sm text-muted-foreground hover:text-foreground hover:bg-accent disabled:opacity-20 transition-colors">
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <button key={p} onClick={() => setPage(p)}
                className={`min-w-[24px] h-6 px-1.5 text-[11px] rounded-sm transition-colors tabular ${
                  p === safePage
                    ? "bg-accent text-foreground border border-[#C9A84C]/40"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/40"
                }`}>
                {p}
              </button>
            ))}
            <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={safePage === totalPages}
              className="p-1 rounded-sm text-muted-foreground hover:text-foreground hover:bg-accent disabled:opacity-20 transition-colors">
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
