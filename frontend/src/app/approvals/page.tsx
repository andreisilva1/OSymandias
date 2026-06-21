"use client";

import { useState } from "react";
import Link from "next/link";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { useTasksByStatus } from "@/hooks/useJobData";
import { api } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import { Loader2, Check, ShieldCheck } from "lucide-react";

export default function ApprovalsPage() {
  const qc = useQueryClient();
  const { data: tasks = [], isLoading } = useTasksByStatus("HUMAN_REVIEW");
  const [approving, setApproving] = useState<string | null>(null);

  const approve = useMutation({
    mutationFn: (t: { job_id: string; id: string }) => api.jobs.approveTask(t.job_id, t.id),
    onMutate: (t) => setApproving(t.id),
    onSettled: () => {
      setApproving(null);
      qc.invalidateQueries({ queryKey: ["tasks", "HUMAN_REVIEW"] });
    },
  });

  return (
    <div className="flex flex-col h-full">
      <div className="page-topbar">
        <div>
          <div className="page-title">Approvals</div>
          <div className="page-sub">Tasks awaiting human review · {tasks.length} pending</div>
        </div>
        {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: "#607080" }} />}
      </div>

      <div className="page-content">
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {tasks.map((t) => (
            <div key={t.id} className="flex items-center justify-between p-3 border border-border bg-card rounded-[var(--radius)]">
              <div className="min-w-0 flex-1">
                <div className="text-[13px] text-foreground truncate">{t.title}</div>
                <div className="text-[11px] text-muted-foreground/60 mt-0.5">
                  <span className="text-amber">{t.agent_type ?? "—"}</span>
                  <span className="mx-2 text-muted-foreground/30">·</span>
                  <Link href={`/jobs/${t.job_id}`} className="font-mono hover:text-foreground transition-colors">
                    job {t.job_id.slice(0, 8)}
                  </Link>
                  <span className="mx-2 text-muted-foreground/30">·</span>
                  {formatRelative(t.created_at)}
                </div>
              </div>
              <button
                onClick={() => approve.mutate({ job_id: t.job_id, id: t.id })}
                disabled={approving === t.id}
                className="ml-3 shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium border border-[#C9A84C]/50 text-[#C9A84C] rounded-[var(--radius)] hover:bg-[#C9A84C]/10 transition-colors disabled:opacity-50"
              >
                {approving === t.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                approve
              </button>
            </div>
          ))}

          {tasks.length === 0 && !isLoading && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, padding: "64px 0", color: "#607080" }}>
              <ShieldCheck className="w-7 h-7" style={{ color: "#3A4858" }} />
              <div style={{ fontSize: 13 }}>Nothing awaiting approval.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
