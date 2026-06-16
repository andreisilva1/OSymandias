"use client";

import { useState } from "react";
import { useMemory } from "@/hooks/useJobData";
import { Loader2 } from "lucide-react";

const SCOPES = ["ALL", "TASK", "JOB", "GLOBAL"];

const SCOPE_COLOR: Record<string, string> = {
  TASK: "text-cyan",
  JOB: "text-amber",
  GLOBAL: "text-purple",
};

export default function MemoryLayerPage() {
  const [scope, setScope] = useState("ALL");
  const { data: entries = [], isLoading } = useMemory({
    scope: scope === "ALL" ? undefined : scope,
    limit: 200,
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
        <div>
          <div className="text-[9px] tracking-[0.15em] text-muted-foreground/40 uppercase mb-0.5">MEMORY / LAYER</div>
          <h1 className="text-sm font-semibold text-bright">Memory Explorer</h1>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          {isLoading && <Loader2 className="w-3 h-3 animate-spin" />}
          <span className="tabular">{entries.length} entries</span>
        </div>
      </div>

      {/* Scope filter */}
      <div className="flex items-center gap-px px-5 py-2 border-b border-border shrink-0 bg-card/50">
        {SCOPES.map((s) => (
          <button key={s} onClick={() => setScope(s)}
            className={`px-3 py-1 text-[10px] tracking-wide transition-colors ${
              scope === s
                ? "text-foreground bg-accent border-b border-[#C9A84C]"
                : "text-muted-foreground hover:text-foreground"
            }`}>
            {s}
          </button>
        ))}
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[70px_100px_160px_1fr_60px_100px] gap-3 px-5 py-2 text-[9px] tracking-[0.1em] text-muted-foreground/30 uppercase border-b border-border bg-background/95 sticky top-0 shrink-0">
        <span>SCOPE</span>
        <span>SCOPE ID</span>
        <span>KEY</span>
        <span>VALUE</span>
        <span>READS</span>
        <span>CREATED</span>
      </div>

      {/* Entries */}
      <div className="flex-1 overflow-auto divide-y divide-border/30">
        {entries.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted-foreground/30">
            <div className="text-[11px]">no memory entries yet</div>
            <div className="text-[10px]">entries appear after agents write to job or task memory</div>
          </div>
        )}
        {entries.map((entry) => (
          <details key={entry.id} className="group">
            <summary className="grid grid-cols-[70px_100px_160px_1fr_60px_100px] gap-3 px-5 py-2 hover:bg-accent/40 cursor-pointer list-none items-center transition-colors">
              <span className={`text-[10px] font-medium ${SCOPE_COLOR[entry.scope] ?? "text-muted-foreground"}`}>
                {entry.scope}
              </span>
              <span className="text-[10px] text-muted-foreground/50 font-mono truncate">
                {entry.scope_id ? entry.scope_id.slice(0, 8) : "—"}
              </span>
              <span className="text-[10px] font-mono text-foreground truncate">{entry.key}</span>
              <span className="text-[10px] text-muted-foreground/60 truncate font-mono">
                {JSON.stringify(entry.value).slice(0, 80)}
              </span>
              <span className="text-[10px] text-muted-foreground/40 tabular">{entry.access_count}</span>
              <span className="text-[10px] text-muted-foreground/40 tabular">
                {new Date(entry.created_at).toLocaleTimeString()}
              </span>
            </summary>
            <div className="px-5 pb-3 bg-accent/20 border-b border-border/30">
              <pre className="text-[10px] text-muted-foreground/70 font-mono leading-relaxed overflow-auto max-h-48 p-3 bg-background border border-border/50 mt-2">
                {JSON.stringify(entry.value, null, 2)}
              </pre>
              {entry.last_accessed_at && (
                <div className="text-[9px] text-muted-foreground/30 mt-1.5">
                  last accessed: {new Date(entry.last_accessed_at).toLocaleString()}
                </div>
              )}
            </div>
          </details>
        ))}
      </div>

      {/* Stats footer */}
      {entries.length > 0 && (
        <div className="border-t border-border px-5 py-2 flex items-center gap-6 text-[10px] text-muted-foreground shrink-0 bg-card/50">
          {(["TASK", "JOB", "GLOBAL"] as const).map((s) => (
            <span key={s}>
              {s.toLowerCase()}: <span className={`tabular ${SCOPE_COLOR[s]}`}>
                {entries.filter((e) => e.scope === s).length}
              </span>
            </span>
          ))}
          <span className="ml-auto text-muted-foreground/30">refreshes every 10s</span>
        </div>
      )}
    </div>
  );
}
