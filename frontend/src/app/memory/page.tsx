"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { useMemory } from "@/hooks/useJobData";
import { api } from "@/lib/api";
import { Loader2, Trash2, Search } from "lucide-react";

const SCOPES = ["ALL", "TASK", "JOB", "GLOBAL"] as const;

const SCOPE_COLOR: Record<string, string> = {
  TASK: "#5090A8",
  JOB: "#C8A040",
  GLOBAL: "#7870A0",
};

export default function MemoryLayerPage() {
  const qc = useQueryClient();
  const [scope, setScope] = useState("ALL");
  const [search, setSearch] = useState("");
  const { data: entries = [], isLoading } = useMemory({
    scope: scope === "ALL" ? undefined : scope,
    limit: 500,
  });

  const { mutate: deleteEntry } = useMutation({
    mutationFn: (id: string) => api.memory.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memory"] }),
  });

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((e) => {
      const keyMatch = e.key.toLowerCase().includes(q);
      const valMatch = JSON.stringify(e.value).toLowerCase().includes(q);
      return keyMatch || valMatch;
    });
  }, [entries, search]);

  return (
    <div className="flex flex-col h-full">
      {/* Topbar */}
      <div className="page-topbar">
        <div>
          <div className="page-title">Memory Layer</div>
          <div className="page-sub">
            {filtered.length !== entries.length
              ? `${filtered.length} of ${entries.length} entries`
              : `${entries.length} entries`}
          </div>
        </div>
        {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: "#607080" }} />}
      </div>

      <div className="page-content" style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Filter bar */}
        <div className="filter-bar" style={{ gap: 10 }}>
          <div className="search-wrap" style={{ flex: 1, maxWidth: 320 }}>
            <Search style={{ width: 13, height: 13, color: "#384858", flexShrink: 0 }} />
            <input
              className="search-bar"
              placeholder="search key or value..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div style={{ display: "flex", gap: 4 }}>
            {SCOPES.map((s) => (
              <button key={s} onClick={() => setScope(s)}
                className={`filter-select`}
                style={{
                  background: scope === s ? "rgba(200,160,64,0.08)" : undefined,
                  color: scope === s ? "#C8A040" : undefined,
                  borderColor: scope === s ? "rgba(200,160,64,0.25)" : undefined,
                  cursor: "pointer",
                  padding: "5px 12px",
                  fontSize: 11,
                }}>
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Column headers */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "70px 110px 180px 1fr 60px 110px 36px",
          gap: 12, padding: "7px 20px",
          fontSize: 9, fontWeight: 600, letterSpacing: "0.1em",
          color: "#283040", textTransform: "uppercase",
          borderBottom: "1px solid #1E2830",
          background: "rgba(12,16,24,0.8)",
          flexShrink: 0,
        }}>
          <span>Scope</span>
          <span>Scope ID</span>
          <span>Key</span>
          <span>Value</span>
          <span>Reads</span>
          <span>Created</span>
          <span></span>
        </div>

        {/* Entries */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {filtered.length === 0 && !isLoading && (
            <div style={{
              display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", padding: "64px 0", gap: 8,
              color: "#283040",
            }}>
              <div style={{ fontSize: 11 }}>
                {search ? "no entries match the search" : "no memory entries yet"}
              </div>
              {!search && (
                <div style={{ fontSize: 10, color: "#1E2830" }}>
                  entries appear after agents write to job or task memory
                </div>
              )}
            </div>
          )}

          {filtered.map((entry) => {
            const scopeColor = SCOPE_COLOR[entry.scope] ?? "#607080";
            const isLinkable = (entry.scope === "JOB" || entry.scope === "TASK") && entry.scope_id;

            return (
              <details key={entry.id} className="group" style={{ borderBottom: "1px solid rgba(30,40,48,0.5)" }}>
                <summary style={{
                  display: "grid",
                  gridTemplateColumns: "70px 110px 180px 1fr 60px 110px 36px",
                  gap: 12, padding: "8px 20px",
                  cursor: "pointer", listStyle: "none",
                  alignItems: "center",
                  transition: "background 0.15s",
                }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#182028")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <span style={{ fontSize: 10, fontWeight: 600, color: scopeColor }}>
                    {entry.scope}
                  </span>

                  <span style={{ fontSize: 10, fontFamily: "monospace", color: "#607080", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {entry.scope_id ? (
                      isLinkable ? (
                        <Link
                          href={`/jobs/${entry.scope_id}`}
                          onClick={(e) => e.stopPropagation()}
                          style={{ color: "#5090A8", textDecoration: "none" }}
                          onMouseEnter={(e) => (e.currentTarget.style.color = "#C8A040")}
                          onMouseLeave={(e) => (e.currentTarget.style.color = "#5090A8")}
                        >
                          {entry.scope_id.slice(0, 8)}
                        </Link>
                      ) : (
                        entry.scope_id.slice(0, 8)
                      )
                    ) : "—"}
                  </span>

                  <span style={{ fontSize: 10, fontFamily: "monospace", color: "#D8E0E8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {entry.key}
                  </span>

                  <span style={{ fontSize: 10, fontFamily: "monospace", color: "#607080", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {JSON.stringify(entry.value).slice(0, 80)}
                  </span>

                  <span style={{ fontSize: 10, color: "#384858", fontVariantNumeric: "tabular-nums" }}>
                    {entry.access_count}
                  </span>

                  <span style={{ fontSize: 10, color: "#384858", fontVariantNumeric: "tabular-nums" }}>
                    {new Date(entry.created_at).toLocaleTimeString()}
                  </span>

                  <button
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); deleteEntry(entry.id); }}
                    title="Delete entry"
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      color: "#283040", padding: 4, borderRadius: 4, display: "flex", alignItems: "center",
                      transition: "color 0.15s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "#C06070")}
                    onMouseLeave={(e) => (e.currentTarget.style.color = "#283040")}
                  >
                    <Trash2 style={{ width: 12, height: 12 }} />
                  </button>
                </summary>

                <div style={{
                  padding: "8px 20px 12px",
                  background: "rgba(18,24,32,0.6)",
                  borderTop: "1px solid #1E2830",
                }}>
                  <pre style={{
                    fontSize: 10, fontFamily: "monospace", color: "#607080",
                    lineHeight: 1.6, overflowX: "auto", maxHeight: 192,
                    padding: 12, background: "#0C1018",
                    border: "1px solid #1E2830", borderRadius: 6,
                    marginTop: 4,
                  }}>
                    {JSON.stringify(entry.value, null, 2)}
                  </pre>
                  {entry.last_accessed_at && (
                    <div style={{ fontSize: 9, color: "#283040", marginTop: 6 }}>
                      last accessed: {new Date(entry.last_accessed_at).toLocaleString()}
                    </div>
                  )}
                  {entry.expires_at && (
                    <div style={{ fontSize: 9, color: "#384858", marginTop: 2 }}>
                      expires: {new Date(entry.expires_at).toLocaleString()}
                    </div>
                  )}
                </div>
              </details>
            );
          })}
        </div>

        {/* Footer */}
        {entries.length > 0 && (
          <div style={{
            borderTop: "1px solid #1E2830", padding: "8px 20px",
            display: "flex", alignItems: "center", gap: 20,
            fontSize: 10, color: "#607080", background: "rgba(12,16,24,0.8)",
            flexShrink: 0,
          }}>
            {(["TASK", "JOB", "GLOBAL"] as const).map((s) => (
              <span key={s}>
                {s.toLowerCase()}:{" "}
                <span style={{ color: SCOPE_COLOR[s], fontVariantNumeric: "tabular-nums" }}>
                  {entries.filter((e) => e.scope === s).length}
                </span>
              </span>
            ))}
            <span style={{ marginLeft: "auto", color: "#283040" }}>refreshes every 10s</span>
          </div>
        )}
      </div>
    </div>
  );
}
