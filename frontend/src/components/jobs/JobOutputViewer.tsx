"use client";

import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Clipboard, Code2, Eye, Download } from "lucide-react";

const AGENT_COLORS: Record<string, string> = {
  ResearchAgent:  "text-cyan   border-cyan/20   bg-cyan/5",
  AnalystAgent:   "text-purple border-purple/20 bg-purple/5",
  WriterAgent:    "text-green  border-green/20  bg-green/5",
  EvaluatorAgent: "text-amber  border-amber/20  bg-amber/5",
  PlannerAgent:   "text-blue   border-blue/20   bg-blue/5",
};

function agentColor(type?: string) {
  if (!type) return "text-muted-foreground border-border bg-card";
  return AGENT_COLORS[type] ?? "text-muted-foreground border-border bg-card";
}

function CopyButton({ text, small }: { text: string; small?: boolean }) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }, [text]);

  return (
    <button
      onClick={copy}
      title="Copy to clipboard"
      className={`flex items-center gap-1 transition-colors ${
        small
          ? "text-muted-foreground/40 hover:text-muted-foreground text-[10px]"
          : "text-muted-foreground/50 hover:text-foreground text-[11px]"
      }`}
    >
      {copied ? (
        <Check className={small ? "w-3 h-3 text-green" : "w-3.5 h-3.5 text-green"} />
      ) : (
        <Clipboard className={small ? "w-3 h-3" : "w-3.5 h-3.5"} />
      )}
      {!small && <span>{copied ? "copied" : "copy"}</span>}
    </button>
  );
}

function extractContent(result: unknown): { text: string; isMarkdown: boolean } {
  if (!result || typeof result !== "object") {
    return { text: typeof result === "string" ? result : JSON.stringify(result, null, 2), isMarkdown: false };
  }
  const r = result as Record<string, unknown>;
  const text =
    (typeof r.content === "string" && r.content) ||
    (typeof r.summary === "string" && r.summary) ||
    (typeof r.analysis === "string" && r.analysis) ||
    (typeof r.report === "string" && r.report) ||
    (typeof r.text === "string" && r.text) ||
    "";

  if (text) {
    const looksLikeMarkdown = /^#{1,3} |^\*\*|^\- |\n#{1,3} |\|.+\|/.test(text);
    return { text, isMarkdown: looksLikeMarkdown };
  }
  return { text: JSON.stringify(result, null, 2), isMarkdown: false };
}

interface TaskOutput {
  title: string;
  agentType?: string;
  result: unknown;
}

interface JobOutputViewerProps {
  outputPayload: Record<string, unknown> | null | undefined;
  tasks?: { title: string; agent_type?: string }[];
}

export function JobOutputViewer({ outputPayload, tasks = [] }: JobOutputViewerProps) {
  const [viewRaw, setViewRaw]       = useState(false);
  const [expanded, setExpanded]     = useState<Record<string, boolean>>({});
  const [copiedAll, setCopiedAll]   = useState(false);

  if (!outputPayload || Object.keys(outputPayload).length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-[12px] text-muted-foreground/30 border border-border rounded-[var(--radius)]">
        no output yet — process still running
      </div>
    );
  }

  // Build ordered list matching task order when possible
  const taskMap = Object.fromEntries(tasks.map((t) => [t.title, t.agent_type]));
  const entries: TaskOutput[] = Object.entries(outputPayload).map(([title, result]) => ({
    title,
    agentType: taskMap[title],
    result,
  }));

  const allJson = JSON.stringify(outputPayload, null, 2);

  const downloadJson = () => {
    const blob = new Blob([allJson], { type: "application/json" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = "output.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const copyAll = () => {
    navigator.clipboard.writeText(allJson).then(() => {
      setCopiedAll(true);
      setTimeout(() => setCopiedAll(false), 1800);
    });
  };

  const toggleAll = (open: boolean) => {
    setExpanded(Object.fromEntries(entries.map((e) => [e.title, open])));
  };

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="os-label">{entries.length} task output{entries.length !== 1 ? "s" : ""}</span>
          <button
            onClick={() => toggleAll(true)}
            className="text-[10px] text-muted-foreground/40 hover:text-muted-foreground transition-colors"
          >
            expand all
          </button>
          <span className="text-muted-foreground/20">·</span>
          <button
            onClick={() => toggleAll(false)}
            className="text-[10px] text-muted-foreground/40 hover:text-muted-foreground transition-colors"
          >
            collapse all
          </button>
        </div>

        <div className="flex items-center gap-3">
          {/* Toggle raw / rendered */}
          <button
            onClick={() => setViewRaw((v) => !v)}
            className="flex items-center gap-1.5 text-[11px] text-muted-foreground/50 hover:text-foreground transition-colors"
            title={viewRaw ? "Switch to rendered view" : "Switch to raw JSON"}
          >
            {viewRaw ? <Eye className="w-3.5 h-3.5" /> : <Code2 className="w-3.5 h-3.5" />}
            {viewRaw ? "rendered" : "raw JSON"}
          </button>

          {/* Copy all */}
          <button
            onClick={copyAll}
            className="flex items-center gap-1.5 text-[11px] text-muted-foreground/50 hover:text-foreground transition-colors"
          >
            {copiedAll ? (
              <Check className="w-3.5 h-3.5 text-green" />
            ) : (
              <Clipboard className="w-3.5 h-3.5" />
            )}
            {copiedAll ? "copied" : "copy all"}
          </button>

          {/* Download */}
          <button
            onClick={downloadJson}
            className="flex items-center gap-1.5 text-[11px] text-muted-foreground/50 hover:text-foreground transition-colors"
            title="Download output as JSON"
          >
            <Download className="w-3.5 h-3.5" />
            download
          </button>
        </div>
      </div>

      {/* Raw JSON view */}
      {viewRaw && (
        <pre className="text-[11px] bg-background border border-border rounded-[var(--radius)] p-4 overflow-auto leading-relaxed font-mono text-muted-foreground max-h-[70vh]">
          {allJson}
        </pre>
      )}

      {/* Per-task cards */}
      {!viewRaw && entries.map((entry) => {
        const { text, isMarkdown } = extractContent(entry.result);
        const isOpen = expanded[entry.title] ?? true;
        const color  = agentColor(entry.agentType);

        return (
          <div
            key={entry.title}
            className="border border-border rounded-[var(--radius)] overflow-hidden"
          >
            {/* Card header */}
            <button
              onClick={() => setExpanded((prev) => ({ ...prev, [entry.title]: !isOpen }))}
              className="w-full flex items-center justify-between px-4 py-3 bg-card hover:bg-accent/50 transition-colors text-left"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span
                  className={`text-[10px] tracking-wider uppercase font-medium px-2 py-0.5 rounded border ${color} shrink-0`}
                >
                  {entry.agentType ?? "agent"}
                </span>
                <span className="text-[13px] font-medium text-foreground truncate">
                  {entry.title}
                </span>
              </div>

              <div className="flex items-center gap-3 ml-3 shrink-0">
                <CopyButton text={text} small />
                <span className="text-[10px] text-muted-foreground/30 transition-transform duration-150"
                  style={{ transform: isOpen ? "rotate(90deg)" : "rotate(0deg)" }}>
                  ▶
                </span>
              </div>
            </button>

            {/* Card body */}
            {isOpen && (
              <div className="border-t border-border/50">
                {isMarkdown ? (
                  <div className="px-5 py-4 prose prose-sm prose-invert max-w-none
                    prose-headings:text-foreground prose-headings:font-semibold
                    prose-p:text-muted-foreground prose-p:text-[13px] prose-p:leading-relaxed
                    prose-strong:text-foreground
                    prose-code:text-amber prose-code:bg-background prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-[11px]
                    prose-pre:bg-background prose-pre:border prose-pre:border-border prose-pre:text-[11px]
                    prose-table:text-[12px] prose-th:text-muted-foreground prose-td:text-muted-foreground/80
                    prose-li:text-muted-foreground prose-li:text-[13px]
                    prose-a:text-cyan prose-a:no-underline hover:prose-a:underline
                    prose-blockquote:border-l-[#C9A84C] prose-blockquote:text-muted-foreground">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
                  </div>
                ) : (
                  <pre className="text-[11px] bg-background text-muted-foreground/80 px-5 py-4 overflow-auto leading-relaxed font-mono max-h-[60vh]">
                    {text}
                  </pre>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
