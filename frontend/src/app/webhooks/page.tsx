"use client";

import { useState } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { useWebhooks } from "@/hooks/useJobData";
import { api } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import { Plus, Loader2, Trash2 } from "lucide-react";

const LIFECYCLE_EVENTS = ["JOB_COMPLETED", "JOB_FAILED", "JOB_CANCELLED", "JOB_BUDGET_EXCEEDED"] as const;

export default function WebhooksPage() {
  const qc = useQueryClient();
  const { data: webhooks = [], isLoading } = useWebhooks();
  const [url, setUrl] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [err, setErr] = useState("");

  const create = useMutation({
    mutationFn: () => api.webhooks.create({ url, events: selected.length ? selected : null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["webhooks"] });
      setUrl(""); setSelected([]); setErr("");
    },
    onError: (e: unknown) => setErr(e instanceof Error ? e.message : "Failed to create webhook"),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.webhooks.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["webhooks"] }),
  });

  function toggle(ev: string) {
    setSelected((s) => (s.includes(ev) ? s.filter((x) => x !== ev) : [...s, ev]));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    create.mutate();
  }

  return (
    <div className="flex flex-col h-full">
      <div className="page-topbar">
        <div>
          <div className="page-title">Webhooks</div>
          <div className="page-sub">Lifecycle event subscribers · {webhooks.length} registered</div>
        </div>
        {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: "#607080" }} />}
      </div>

      <div className="page-content space-y-5">
        {/* Create form */}
        <form onSubmit={submit} className="os-card p-4 space-y-3">
          <div>
            <label className="os-label block mb-1.5">ENDPOINT URL</label>
            <input value={url} onChange={(e) => { setUrl(e.target.value); setErr(""); }}
              className="os-input" placeholder="https://example.com/hook" />
          </div>
          <div>
            <label className="os-label block mb-1.5">EVENTS <span style={{ color: "#384858", textTransform: "none", letterSpacing: 0, fontSize: 10 }}>(none = all)</span></label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {LIFECYCLE_EVENTS.map((ev) => (
                <button key={ev} type="button" onClick={() => toggle(ev)}
                  className={`status-badge ${selected.includes(ev) ? "badge-running" : ""}`}
                  style={{ cursor: "pointer", opacity: selected.includes(ev) ? 1 : 0.5 }}>
                  {ev}
                </button>
              ))}
            </div>
          </div>
          {err && <p style={{ fontSize: 11, color: "#C06070" }}>{err}</p>}
          <div className="flex justify-end">
            <button type="submit" disabled={create.isPending || !url.trim()} className="btn btn-primary"
              style={{ opacity: create.isPending || !url.trim() ? 0.4 : 1 }}>
              {create.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus style={{ width: 14, height: 14 }} />}
              Register
            </button>
          </div>
        </form>

        {/* List */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {webhooks.map((h) => (
            <div key={h.id} className="flex items-center justify-between p-3 border border-border bg-card rounded-[var(--radius)]">
              <div className="min-w-0 flex-1">
                <div className="text-[12.5px] text-foreground font-mono truncate">{h.url}</div>
                <div className="text-[11px] text-muted-foreground/60 mt-0.5">
                  {h.events?.length ? h.events.join(" · ") : "all events"} · {formatRelative(h.created_at)}
                </div>
              </div>
              <button onClick={() => remove.mutate(h.id)} disabled={remove.isPending}
                className="ml-3 shrink-0 p-1.5 text-muted-foreground hover:text-red transition-colors">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          {webhooks.length === 0 && !isLoading && (
            <div style={{ padding: "48px 0", textAlign: "center", fontSize: 13, color: "#607080" }}>
              No webhooks registered.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
