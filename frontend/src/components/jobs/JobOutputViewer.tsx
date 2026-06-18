"use client";

import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Clipboard, Code2, Eye, Download, X, Radio } from "lucide-react";

interface MediaItem {
  type: "image" | "pdf";
  url?: string;
  base64?: string;
  caption?: string;
  title?: string;
}

function MediaGallery({ items }: { items: MediaItem[] }) {
  const [lightbox, setLightbox] = useState<string | null>(null);

  return (
    <>
      <div className="flex flex-wrap gap-3 px-5 py-3 border-t border-border/50">
        {items.map((item, i) => {
          const src = item.base64 ?? item.url ?? "";
          if (item.type === "image") {
            return (
              <div key={i} className="flex flex-col gap-1">
                <img
                  src={src}
                  alt={item.caption ?? `image-${i}`}
                  className="max-h-40 rounded border border-border cursor-zoom-in object-contain bg-background"
                  onClick={() => setLightbox(src)}
                />
                {item.caption && (
                  <span className="text-[10px] text-muted-foreground text-center">{item.caption}</span>
                )}
              </div>
            );
          }
          if (item.type === "pdf") {
            return (
              <a
                key={i}
                href={src}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-[11px] text-cyan border border-border/50 rounded px-3 py-2 hover:bg-accent/40 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                {item.title ?? `document-${i}.pdf`}
              </a>
            );
          }
          return null;
        })}
      </div>

      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setLightbox(null)}
        >
          <button
            className="absolute top-4 right-4 text-white/60 hover:text-white"
            onClick={() => setLightbox(null)}
          >
            <X className="w-6 h-6" />
          </button>
          <img
            src={lightbox}
            alt="lightbox"
            className="max-w-[90vw] max-h-[90vh] rounded object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
}

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
  liveProgress?: Record<string, unknown>;
}

export function JobOutputViewer({ outputPayload, tasks = [], liveProgress = {} }: JobOutputViewerProps) {
  const [viewRaw, setViewRaw]       = useState(false);
  const [expanded, setExpanded]     = useState<Record<string, boolean>>({});
  const [copiedAll, setCopiedAll]   = useState(false);

  const hasOutput = outputPayload && Object.keys(outputPayload).length > 0;
  const hasLive   = Object.keys(liveProgress).length > 0;

  if (!hasOutput) {
    if (!hasLive) {
      return (
        <div className="flex items-center justify-center py-16 text-[12px] text-muted-foreground/30 border border-border rounded-[var(--radius)]">
          no output yet — process still running
        </div>
      );
    }

    // Live preview: show latest TASK_PROGRESS payloads while still running
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-[11px] text-amber">
          <Radio className="w-3.5 h-3.5 animate-pulse" />
          <span className="os-label">live progress</span>
        </div>
        {Object.entries(liveProgress).map(([title, payload]) => {
          const { text } = extractContent(payload);
          const taskMeta = tasks.find((t) => t.title === title);
          const color = agentColor(taskMeta?.agent_type);
          return (
            <div key={title} className="border border-amber/20 rounded-[var(--radius)] overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-2.5 bg-amber/5">
                <span className={`text-[10px] tracking-wider uppercase font-medium px-2 py-0.5 rounded border ${color} shrink-0`}>
                  {taskMeta?.agent_type ?? "agent"}
                </span>
                <span className="text-[12px] font-medium text-foreground truncate">{title}</span>
                <span className="ml-auto text-[10px] text-amber/60 tabular font-mono animate-pulse">running</span>
              </div>
              <pre className="text-[11px] bg-background text-muted-foreground/70 px-5 py-3 overflow-auto leading-relaxed font-mono max-h-40 border-t border-amber/10">
                {text}
              </pre>
            </div>
          );
        })}
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
                {Array.isArray((entry.result as Record<string, unknown>)?._media) && (
                  <MediaGallery items={(entry.result as Record<string, unknown>)._media as MediaItem[]} />
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
