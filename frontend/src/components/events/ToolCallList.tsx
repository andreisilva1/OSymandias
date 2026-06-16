"use client";

import { useState } from "react";
import type { ToolCall } from "@/types";
import { StatusBadge } from "@/components/jobs/JobStatusBadge";
import { formatDuration, formatDate } from "@/lib/utils";
import { ChevronDown, ChevronRight } from "lucide-react";

interface Props {
  toolCalls: ToolCall[];
}

export function ToolCallList({ toolCalls }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">Tool Calls</h2>
        <span className="text-xs text-muted-foreground">{toolCalls.length} calls</span>
      </div>

      <div className="rounded-lg border border-border overflow-hidden divide-y divide-border">
        {toolCalls.map((tc) => (
          <div key={tc.id}>
            <button
              className="w-full flex items-center gap-3 px-4 py-3 hover:bg-accent/20 transition-colors text-left"
              onClick={() => setExpanded(expanded === tc.id ? null : tc.id)}
            >
              {expanded === tc.id ? (
                <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
              )}
              <span className="text-xs font-mono font-medium text-amber-400 w-36 shrink-0">
                {tc.tool_name}
              </span>
              <StatusBadge status={tc.status} />
              <span className="text-xs text-muted-foreground ml-auto">
                {tc.duration_ms ? formatDuration(tc.duration_ms) : "—"}
              </span>
              <span className="text-xs text-muted-foreground w-28 text-right shrink-0">
                {formatDate(tc.created_at)}
              </span>
            </button>

            {expanded === tc.id && (
              <div className="px-4 pb-3 grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Input</p>
                  <pre className="text-xs bg-black/30 rounded p-2 border border-border overflow-auto max-h-32">
                    {JSON.stringify(tc.input_args, null, 2)}
                  </pre>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Output</p>
                  <pre className="text-xs bg-black/30 rounded p-2 border border-border overflow-auto max-h-32">
                    {tc.output_result ? JSON.stringify(tc.output_result, null, 2) : tc.error_message ?? "—"}
                  </pre>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
