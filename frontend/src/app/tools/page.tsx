"use client";

import { useState } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { useTools } from "@/hooks/useJobData";
import { api } from "@/lib/api";
import { Plus, Loader2, X, ChevronRight } from "lucide-react";
import type { ToolDefinition } from "@/types";

const inp = "w-full bg-background border border-border px-3 py-2 text-sm focus:outline-none focus:border-[#C9A84C]";
const lbl = "text-[10px] text-muted-foreground uppercase tracking-wider block mb-1";

const SCHEMA_PLACEHOLDER = JSON.stringify(
  { type: "object", properties: { query: { type: "string", description: "Input value" } }, required: ["query"] },
  null, 2
);

// ── Register modal ────────────────────────────────────────────────────────────
function RegisterModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "", description: "", webhook_url: "",
    rate_limit_per_minute: "" as string | number,
    requires_external_api: true,
  });
  const [inputSchema, setInputSchema] = useState(SCHEMA_PLACEHOLDER);
  const [outputSchema, setOutputSchema] = useState('{"type": "object"}');
  const [err, setErr] = useState("");

  const { mutate, isPending } = useMutation({
    mutationFn: () => {
      const input_schema = JSON.parse(inputSchema);
      const output_schema = JSON.parse(outputSchema);
      return api.tools.create({
        name: form.name,
        description: form.description,
        webhook_url: form.webhook_url || undefined,
        rate_limit_per_minute: form.rate_limit_per_minute ? Number(form.rate_limit_per_minute) : undefined,
        requires_external_api: form.requires_external_api,
        input_schema,
        output_schema,
      });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tools"] }); onClose(); },
    onError: (e: Error) => setErr(e.message),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("");
    try { JSON.parse(inputSchema); JSON.parse(outputSchema); }
    catch { setErr("Invalid JSON in schema fields"); return; }
    mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div className="bg-card border border-border w-[560px] max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
          <span className="text-[9px] tracking-[0.15em] text-muted-foreground/50 uppercase">REGISTER SYSCALL</span>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
        </div>

        <form onSubmit={submit} className="overflow-auto flex-1 p-5 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={lbl}>NAME <span className="text-red normal-case">*</span></label>
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className={`${inp} font-mono`} placeholder="my_tool" />
            </div>
            <div>
              <label className={lbl}>RATE LIMIT <span className="text-muted-foreground/40 normal-case">/min</span></label>
              <input type="number" min={1} value={form.rate_limit_per_minute}
                onChange={(e) => setForm({ ...form, rate_limit_per_minute: e.target.value })}
                className={inp} placeholder="∞ unlimited" />
            </div>
          </div>

          <div>
            <label className={lbl}>DESCRIPTION <span className="text-red normal-case">*</span></label>
            <input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
              className={inp} placeholder="What this syscall does — shown to the agent" />
          </div>

          <div>
            <label className={lbl}>
              WEBHOOK URL
              <span className="ml-2 text-muted-foreground/40 normal-case tracking-normal font-normal">
                — POST {"{"}tool, input{"}"} → JSON
              </span>
            </label>
            <input value={form.webhook_url} onChange={(e) => setForm({ ...form, webhook_url: e.target.value })}
              className={inp} placeholder="https://your-service.com/webhook" />
            <p className="text-[9px] text-muted-foreground/40 mt-1">
              When the agent calls this syscall, the runtime POSTs <code className="text-amber">{"{ tool, input }"}</code> to this URL and returns the JSON response.
            </p>
          </div>

          <div>
            <label className={lbl}>INPUT SCHEMA <span className="text-muted-foreground/40 normal-case">(JSON Schema)</span></label>
            <textarea value={inputSchema} onChange={(e) => { setInputSchema(e.target.value); setErr(""); }}
              rows={5} className={`${inp} font-mono text-xs resize-none leading-relaxed`} />
          </div>

          <div>
            <label className={lbl}>OUTPUT SCHEMA <span className="text-muted-foreground/40 normal-case">(JSON Schema)</span></label>
            <textarea value={outputSchema} onChange={(e) => { setOutputSchema(e.target.value); setErr(""); }}
              rows={3} className={`${inp} font-mono text-xs resize-none leading-relaxed`} />
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.requires_external_api}
              onChange={(e) => setForm({ ...form, requires_external_api: e.target.checked })}
              className="accent-[#C9A84C]" />
            <span className="text-[10px] text-muted-foreground">requires external network access</span>
          </label>

          {err && <p className="text-[10px] text-red">{err}</p>}
        </form>

        <div className="flex justify-end gap-2 px-5 py-3 border-t border-border shrink-0">
          <button type="button" onClick={onClose} className="px-3 py-1.5 text-xs text-muted-foreground border border-border hover:bg-accent">CANCEL</button>
          <button onClick={submit} disabled={isPending || !form.name.trim() || !form.description.trim()}
            className="flex items-center gap-1 px-3 py-1.5 text-xs border disabled:opacity-40"
            style={{ background: "rgba(201,168,76,0.08)", borderColor: "#C9A84C", color: "#C9A84C" }}>
            {isPending && <Loader2 className="w-3 h-3 animate-spin" />} REGISTER
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Edit panel ────────────────────────────────────────────────────────────────
function EditPanel({ tool, onClose }: { tool: ToolDefinition; onClose: () => void }) {
  const qc = useQueryClient();
  const isBuiltin = !tool.webhook_url && tool.created_at === undefined;
  const [form, setForm] = useState({
    description: tool.description,
    webhook_url: tool.webhook_url ?? "",
    rate_limit_per_minute: tool.rate_limit_per_minute ?? "" as string | number,
    requires_external_api: tool.requires_external_api,
  });
  const [inputSchema, setInputSchema] = useState(JSON.stringify(tool.input_schema, null, 2));
  const [outputSchema, setOutputSchema] = useState(JSON.stringify(tool.output_schema, null, 2));
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState("");

  const { mutate: save, isPending: saving } = useMutation({
    mutationFn: () => {
      const input_schema = JSON.parse(inputSchema);
      const output_schema = JSON.parse(outputSchema);
      return api.tools.update(tool.name, {
        ...form,
        rate_limit_per_minute: form.rate_limit_per_minute ? Number(form.rate_limit_per_minute) : undefined,
        webhook_url: form.webhook_url || undefined,
        input_schema,
        output_schema,
      });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tools"] }); setSaved(true); setTimeout(() => setSaved(false), 2000); },
    onError: (e: Error) => setErr(e.message),
  });

  const { mutate: deactivate, isPending: deactivating } = useMutation({
    mutationFn: () => api.tools.deactivate(tool.name),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tools"] }); onClose(); },
  });

  function handleSave() {
    setErr("");
    try { JSON.parse(inputSchema); JSON.parse(outputSchema); }
    catch { setErr("Invalid JSON in schema fields"); return; }
    save();
  }

  return (
    <div className="w-[420px] shrink-0 border-l border-border flex flex-col bg-card h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <div>
          <div className="text-[11px] font-semibold font-mono" style={{ color: "#f59e0b" }}>{tool.name}()</div>
          <div className="text-[10px] text-muted-foreground/50">
            {tool.webhook_url ? "webhook syscall" : "builtin syscall"}
          </div>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-3">
        <div>
          <label className={lbl}>DESCRIPTION</label>
          <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
            className={inp} disabled={isBuiltin} />
        </div>

        <div>
          <label className={lbl}>
            WEBHOOK URL
            {!tool.webhook_url && <span className="ml-2 text-muted-foreground/30 normal-case">— builtin, no webhook</span>}
          </label>
          <input value={form.webhook_url} onChange={(e) => setForm({ ...form, webhook_url: e.target.value })}
            className={inp} placeholder="https://..." disabled={isBuiltin} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={lbl}>RATE LIMIT /min</label>
            <input type="number" min={1} value={form.rate_limit_per_minute}
              onChange={(e) => setForm({ ...form, rate_limit_per_minute: e.target.value })}
              className={inp} placeholder="∞" />
          </div>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={form.requires_external_api}
                onChange={(e) => setForm({ ...form, requires_external_api: e.target.checked })}
                className="accent-[#C9A84C]" />
              <span className="text-[10px] text-muted-foreground">external network</span>
            </label>
          </div>
        </div>

        <div>
          <label className={lbl}>INPUT SCHEMA</label>
          <textarea value={inputSchema} onChange={(e) => { setInputSchema(e.target.value); setErr(""); }}
            rows={6} className={`${inp} font-mono text-[10px] resize-none leading-relaxed`} />
        </div>

        <div>
          <label className={lbl}>OUTPUT SCHEMA</label>
          <textarea value={outputSchema} onChange={(e) => { setOutputSchema(e.target.value); setErr(""); }}
            rows={4} className={`${inp} font-mono text-[10px] resize-none leading-relaxed`} />
        </div>

        {err && <p className="text-[10px] text-red">{err}</p>}

        <div className="border border-border bg-background p-3 text-[10px] text-muted-foreground/40 space-y-1">
          <div className="flex justify-between">
            <span>status</span>
            <span className={tool.is_active ? "text-green" : "text-red"}>{tool.is_active ? "active" : "inactive"}</span>
          </div>
          {tool.created_at && (
            <div className="flex justify-between">
              <span>registered</span>
              <span>{new Date(tool.created_at).toLocaleDateString()}</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-2 px-4 py-3 border-t border-border shrink-0">
        {tool.is_active && (
          <button onClick={() => deactivate()} disabled={deactivating}
            className="px-3 py-1.5 text-xs border border-border text-muted-foreground hover:border-red hover:text-red transition-colors disabled:opacity-40">
            {deactivating ? <Loader2 className="w-3 h-3 animate-spin" /> : "DEACTIVATE"}
          </button>
        )}
        <button onClick={handleSave} disabled={saving}
          className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-xs border disabled:opacity-40"
          style={saved
            ? { background: "rgba(143,181,160,0.1)", borderColor: "#8FB5A0", color: "#8FB5A0" }
            : { background: "rgba(201,168,76,0.08)", borderColor: "#C9A84C", color: "#C9A84C" }}>
          {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : saved ? "SAVED ✓" : "SAVE CHANGES"}
        </button>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function SyscallRegistryPage() {
  const { data: tools = [], isLoading } = useTools();
  const [showRegister, setShowRegister] = useState(false);
  const [selected, setSelected] = useState<ToolDefinition | null>(null);

  return (
    <div className="flex flex-col h-full">
      {showRegister && <RegisterModal onClose={() => setShowRegister(false)} />}

      <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
        <div>
          <div className="text-[9px] tracking-[0.15em] text-muted-foreground/40 uppercase mb-0.5">SERVICES / SYSCALL REGISTRY</div>
          <h1 className="text-sm font-semibold text-bright">System Calls</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-muted-foreground tabular">
            {tools.length} syscalls {isLoading && <Loader2 className="w-3 h-3 animate-spin inline ml-1" />}
          </span>
          <button onClick={() => setShowRegister(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border hover:border-[#C9A84C] hover:text-[#C9A84C] transition-colors">
            <Plus className="w-3 h-3" /> REGISTER
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="grid grid-cols-[160px_1fr_90px_90px_70px_20px] gap-3 px-5 py-2 text-[9px] tracking-[0.1em] text-muted-foreground/40 uppercase border-b border-border bg-card/50 shrink-0">
            <span>SYSCALL</span>
            <span>DESCRIPTION</span>
            <span>TYPE</span>
            <span>RATE</span>
            <span>STATE</span>
            <span />
          </div>

          <div className="flex-1 overflow-auto divide-y divide-border/50">
            {tools.map((tool) => (
              <button key={tool.name}
                onClick={() => setSelected(selected?.name === tool.name ? null : tool)}
                className={`w-full grid grid-cols-[160px_1fr_90px_90px_70px_20px] gap-3 px-5 py-3 transition-colors items-center text-left ${
                  selected?.name === tool.name ? "bg-accent" : "hover:bg-accent/50"
                }`}>
                <div>
                  <div className="text-[11px] font-mono font-medium" style={{ color: "#f59e0b" }}>{tool.name}</div>
                  {tool.webhook_url && (
                    <div className="text-[9px] text-muted-foreground/40 truncate">webhook</div>
                  )}
                </div>
                <span className="text-[11px] text-muted-foreground leading-relaxed text-left truncate">
                  {tool.description}
                </span>
                <span className="flex items-center gap-1.5">
                  {tool.webhook_url ? (
                    <><span className="dot dot-running" style={{ width: 5, height: 5 }} /><span className="text-[10px] text-cyan">webhook</span></>
                  ) : tool.requires_external_api ? (
                    <><span className="dot dot-amber" /><span className="text-[10px] text-amber">network</span></>
                  ) : (
                    <><span className="dot dot-completed" /><span className="text-[10px] text-muted-foreground">internal</span></>
                  )}
                </span>
                <span className="text-[10px] text-muted-foreground tabular">
                  {tool.rate_limit_per_minute ? `${tool.rate_limit_per_minute}/min` : "∞"}
                </span>
                <span className="flex items-center gap-1.5">
                  <span className={`dot ${tool.is_active ? "dot-running" : "dot-dim"}`} />
                  <span className={`text-[10px] ${tool.is_active ? "text-green" : "text-muted-foreground"}`}>
                    {tool.is_active ? "active" : "off"}
                  </span>
                </span>
                <ChevronRight className={`w-3 h-3 transition-transform ${selected?.name === tool.name ? "rotate-90 text-[#C9A84C]" : "text-muted-foreground/30"}`} />
              </button>
            ))}
            {tools.length === 0 && !isLoading && (
              <div className="flex items-center justify-center py-16 text-[11px] text-muted-foreground/30">
                no syscalls registered
              </div>
            )}
          </div>
        </div>

        {selected && (
          <EditPanel key={selected.name} tool={selected} onClose={() => setSelected(null)} />
        )}
      </div>
    </div>
  );
}
