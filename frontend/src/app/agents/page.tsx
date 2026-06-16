"use client";

import { useState, useMemo } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useAgents, useTools } from "@/hooks/useJobData";
import { api } from "@/lib/api";

import { Plus, Loader2, X, ChevronRight, Copy, Trash2, PowerOff, Power, Download, Upload } from "lucide-react";
import type { AgentDefinition, ToolDefinition } from "@/types";

// ── Shared input styles ───────────────────────────────────────────────────────
const inp = "os-input";
const lbl = "os-label block mb-1.5";

const BUILTIN_AGENTS = new Set([
  "PlannerAgent", "ResearchAgent", "WriterAgent", "AnalystAgent", "EvaluatorAgent",
]);

// ── Provider → model mapping ──────────────────────────────────────────────────
const PROVIDER_MODELS: Record<string, string[]> = {
  ollama:    ["llama3.2"],
  openai:    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo", "o1-mini", "o1-preview"],
  anthropic: ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
  deepseek:  ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
  groq:      ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
  gemini:    ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash-exp"],
};

function ModelSelect({ provider, value, onChange }: { provider: string; value: string; onChange: (v: string) => void }) {
  const fallback = PROVIDER_MODELS[provider] ?? [];
  const { data: fetched, isLoading, isError } = useQuery({
    queryKey: ["provider-models", provider],
    queryFn: () => api.providers.models(provider),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const models = (!isLoading && !isError && fetched && fetched.length > 0) ? fetched : fallback;
  const effectiveValue = models.includes(value) ? value : (models[0] ?? "");

  return (
    <div className="relative">
      <select
        value={effectiveValue}
        onChange={(e) => onChange(e.target.value)}
        className={inp}
        disabled={isLoading}
      >
        {models.map((m) => <option key={m} value={m}>{m}</option>)}
      </select>
      {isLoading && (
        <span className="absolute right-8 top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground/50">
          loading…
        </span>
      )}
    </div>
  );
}

// ── Register modal ────────────────────────────────────────────────────────────
function RegisterModal({ tools, onClose }: { tools: ToolDefinition[]; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "", role: "worker", description: "",
    system_prompt_template: "", llm_provider: "ollama", llm_model: "llama3.2",
    max_iterations: 10, timeout_seconds: 120,
  });
  const [allowedTools, setAllowedTools] = useState<string[]>([]);
  const [err, setErr] = useState("");

  const { mutate, isPending } = useMutation({
    mutationFn: () => api.agents.create({ ...form, allowed_tools: allowedTools }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["agents"] }); onClose(); },
    onError: (e: Error) => setErr(e.message),
  });

  function toggleTool(name: string) {
    setAllowedTools((prev) => prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name]);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div className="bg-card border border-border w-[560px] max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
          <span className="text-[9px] tracking-[0.15em] text-muted-foreground/50 uppercase">REGISTER AGENT</span>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
        </div>

        <div className="overflow-auto flex-1 p-5 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={lbl}>NAME <span className="text-red normal-case">*</span></label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className={inp} placeholder="MyAgent" />
            </div>
            <div>
              <label className={lbl}>ROLE</label>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className={inp}>
                {["worker", "supervisor", "researcher", "writer", "analyst", "evaluator"].map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className={lbl}>DESCRIPTION</label>
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
              className={inp} placeholder="What this agent does..." />
          </div>

          <div>
            <label className={lbl}>SYSTEM PROMPT <span className="text-red normal-case">*</span></label>
            <textarea value={form.system_prompt_template}
              onChange={(e) => setForm({ ...form, system_prompt_template: e.target.value })}
              rows={6} className={`${inp} font-mono text-xs resize-none leading-relaxed`}
              placeholder={"You are a {{role}} agent.\nTask: {{task_description}}\n\nOutput ONLY valid JSON."} />
            <p className="text-[9px] text-muted-foreground/40 mt-1">
              Variables: {"{{task_description}}"}, {"{{job_context}}"}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={lbl}>LLM PROVIDER</label>
              <select value={form.llm_provider}
                onChange={(e) => {
                  const prov = e.target.value;
                  const firstModel = PROVIDER_MODELS[prov]?.[0] ?? "";
                  setForm({ ...form, llm_provider: prov, llm_model: firstModel });
                }}
                className={inp}>
                {Object.keys(PROVIDER_MODELS).map((p) => <option key={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className={lbl}>MODEL</label>
              <ModelSelect provider={form.llm_provider} value={form.llm_model}
                onChange={(v) => setForm({ ...form, llm_model: v })} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={lbl}>MAX ITERATIONS</label>
              <input type="number" min={1} max={100} value={form.max_iterations}
                onChange={(e) => setForm({ ...form, max_iterations: +e.target.value })} className={inp} />
            </div>
            <div>
              <label className={lbl}>TIMEOUT (s)</label>
              <input type="number" min={10} max={600} value={form.timeout_seconds}
                onChange={(e) => setForm({ ...form, timeout_seconds: +e.target.value })} className={inp} />
            </div>
          </div>

          <div>
            <label className={lbl}>ALLOWED SYSCALLS</label>
            <div className="flex flex-wrap gap-1.5 p-3 border border-border rounded-[var(--radius)] bg-background">
              {tools.map((t) => (
                <button key={t.name} onClick={() => toggleTool(t.name)}
                  className={`text-[11px] px-2.5 py-1 border rounded font-mono transition-colors ${
                    allowedTools.includes(t.name)
                      ? "border-amber text-amber bg-amber/10"
                      : "border-border text-muted-foreground hover:border-muted-foreground"
                  }`}>
                  {t.name}
                </button>
              ))}
              {tools.length === 0 && <span className="text-[11px] text-muted-foreground/30">no syscalls registered</span>}
            </div>
          </div>

          {err && <p className="text-[11px] text-red">{err}</p>}
        </div>

        <div className="flex justify-end gap-2 px-5 py-3 border-t border-border shrink-0">
          <button onClick={onClose}
            className="px-4 py-2 text-[12px] text-muted-foreground border border-border rounded-[var(--radius)] hover:bg-accent transition-colors">
            CANCEL
          </button>
          <button onClick={() => mutate()} disabled={isPending || !form.name.trim() || !form.system_prompt_template.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-[12px] border rounded-[var(--radius)] disabled:opacity-40 transition-colors"
            style={{ background: "rgba(201,168,76,0.08)", borderColor: "#C9A84C", color: "#C9A84C" }}>
            {isPending && <Loader2 className="w-3 h-3 animate-spin" />} REGISTER
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Output Schema Editor ──────────────────────────────────────────────────────
type SchemaField = { key: string; type: string; required: boolean };
const FIELD_TYPES = ["string", "number", "boolean", "array", "object"];

function schemaToFields(schema: Record<string, unknown> | undefined): SchemaField[] {
  if (!schema || typeof schema !== "object") return [];
  const props = (schema as Record<string, Record<string, unknown>>).properties ?? {};
  const req: string[] = (schema as { required?: string[] }).required ?? [];
  return Object.entries(props).map(([key, def]) => ({
    key,
    type: (def as { type?: string }).type ?? "string",
    required: req.includes(key),
  }));
}

function fieldsToSchema(fields: SchemaField[]): Record<string, unknown> {
  const properties: Record<string, { type: string }> = {};
  const required: string[] = [];
  for (const f of fields) {
    if (!f.key.trim()) continue;
    properties[f.key.trim()] = { type: f.type };
    if (f.required) required.push(f.key.trim());
  }
  return { type: "object", properties, required };
}

function OutputSchemaEditor({
  fields, onChange,
}: { fields: SchemaField[]; onChange: (f: SchemaField[]) => void }) {
  function update(i: number, patch: Partial<SchemaField>) {
    onChange(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f)));
  }
  function remove(i: number) { onChange(fields.filter((_, idx) => idx !== i)); }
  function add() { onChange([...fields, { key: "", type: "string", required: false }]); }

  return (
    <div className="space-y-1">
      {fields.map((f, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <input
            value={f.key}
            onChange={(e) => update(i, { key: e.target.value })}
            placeholder="field_name"
            className={`${inp} font-mono text-[10px] flex-1 py-0.5 h-6`}
          />
          <select
            value={f.type}
            onChange={(e) => update(i, { type: e.target.value })}
            className={`${inp} text-[10px] py-0.5 h-6 w-24`}>
            {FIELD_TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
          <button
            onClick={() => update(i, { required: !f.required })}
            title={f.required ? "Required" : "Optional"}
            className={`text-[9px] font-semibold px-1.5 h-6 border rounded transition-colors ${
              f.required
                ? "border-amber/60 text-amber bg-amber/10"
                : "border-border text-muted-foreground hover:border-muted-foreground"
            }`}>
            REQ
          </button>
          <button onClick={() => remove(i)} className="text-muted-foreground/40 hover:text-red transition-colors">
            <X className="w-3 h-3" />
          </button>
        </div>
      ))}
      <button onClick={add}
        className="flex items-center gap-1 text-[10px] text-muted-foreground/50 hover:text-muted-foreground transition-colors mt-1">
        <Plus className="w-3 h-3" /> add field
      </button>
    </div>
  );
}

// ── Edit panel ────────────────────────────────────────────────────────────────
function EditPanel({ agent, tools, onClose, onCloned }: { agent: AgentDefinition; tools: ToolDefinition[]; onClose: () => void; onCloned: (a: AgentDefinition) => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    description: agent.description ?? "",
    system_prompt_template: agent.system_prompt_template,
    llm_provider: agent.llm_provider,
    llm_model: agent.llm_model,
    max_iterations: agent.max_iterations,
    timeout_seconds: agent.timeout_seconds,
  });
  const [allowedTools, setAllowedTools] = useState<string[]>(agent.allowed_tools);
  const [schemaFields, setSchemaFields] = useState<SchemaField[]>(() =>
    schemaToFields(agent.output_schema as Record<string, unknown> | undefined)
  );
  const [saved, setSaved] = useState(false);

  const { mutate: save, isPending: saving } = useMutation({
    mutationFn: () => api.agents.update(agent.name, {
      ...form,
      allowed_tools: allowedTools,
      output_schema: schemaFields.length > 0 ? fieldsToSchema(schemaFields) : undefined,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["agents"] }); setSaved(true); setTimeout(() => setSaved(false), 2000); },
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["agents"] });

  function applyOptimistic(next: boolean) {
    qc.setQueryData<AgentDefinition[]>(["agents"], (old) =>
      old?.map((a) => a.name === agent.name ? { ...a, is_active: next } : a) ?? []
    );
  }

  const { mutate: deactivate, isPending: deactivating } = useMutation<void, Error, void>({
    mutationFn: () => api.agents.deactivate(agent.name),
    onMutate: () => applyOptimistic(false),
    onError:   () => invalidate(),
    onSettled: () => { invalidate(); onClose(); },
  });

  const { mutate: reactivate, isPending: reactivating } = useMutation<void, Error, void>({
    mutationFn: () => api.agents.reactivate(agent.name),
    onMutate: () => applyOptimistic(true),
    onError:   () => invalidate(),
    onSettled: () => { invalidate(); onClose(); },
  });

  const { mutate: hardDelete, isPending: deleting } = useMutation<void, Error, void>({
    mutationFn: () => api.agents.delete(agent.name),
    onMutate: () => {
      qc.setQueryData<AgentDefinition[]>(["agents"], (old) =>
        old?.filter((a) => a.name !== agent.name) ?? []
      );
      onClose();
    },
    onError:   () => invalidate(),
    onSettled: () => invalidate(),
  });

  const { mutate: clone, isPending: cloning } = useMutation({
    mutationFn: () => api.agents.clone(agent.name),
    onSuccess: async (cloned) => { await invalidate(); onCloned(cloned); },
  });

  const isBuiltin = BUILTIN_AGENTS.has(agent.name);

  // ── Export / Import JSON ─────────────────────────────────────────────────────
  function exportJson() {
    const data = {
      name: agent.name,
      version: agent.version,
      role: agent.role,
      ...form,
      allowed_tools: allowedTools,
      output_schema: schemaFields.length > 0 ? fieldsToSchema(schemaFields) : undefined,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${agent.name}.json`; a.click();
    URL.revokeObjectURL(url);
  }

  function importJson(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    file.text().then((text) => {
      try {
        const data = JSON.parse(text);
        setForm({
          description: data.description ?? "",
          system_prompt_template: data.system_prompt_template ?? form.system_prompt_template,
          llm_provider: data.llm_provider ?? form.llm_provider,
          llm_model: data.llm_model ?? form.llm_model,
          max_iterations: data.max_iterations ?? form.max_iterations,
          timeout_seconds: data.timeout_seconds ?? form.timeout_seconds,
        });
        if (Array.isArray(data.allowed_tools)) setAllowedTools(data.allowed_tools);
        if (data.output_schema) setSchemaFields(schemaToFields(data.output_schema));
      } catch { /* ignore invalid JSON */ }
    });
    e.target.value = "";
  }

  // ── Prompt preview ──────────────────────────────────────────────────────────
  const [promptTab, setPromptTab] = useState<"template" | "preview">("template");
  const DEFAULT_VARS: Record<string, string> = {
    task_description: "Research the top 5 AI frameworks in 2025 and summarize key differences.",
    job_context: "Job: Market Research Report · Priority: HIGH",
  };
  const [previewVars, setPreviewVars] = useState<Record<string, string>>(DEFAULT_VARS);

  const detectedVars = useMemo(() => {
    const matches = [...form.system_prompt_template.matchAll(/\{\{(\w+)\}\}/g)];
    return [...new Set(matches.map((m) => m[1]))];
  }, [form.system_prompt_template]);

  const previewHtml = useMemo(() => {
    let out = form.system_prompt_template
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    out = out.replace(/\{\{(\w+)\}\}/g, (_match, key) => {
      const val = previewVars[key];
      return val
        ? `<mark class="var-known">${val}</mark>`
        : `<mark class="var-unknown">{{${key}}}</mark>`;
    });
    return out.replace(/\n/g, "<br/>");
  }, [form.system_prompt_template, previewVars]);

  function toggleTool(name: string) {
    setAllowedTools((prev) => prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name]);
  }

  return (
    <div className="w-[420px] shrink-0 border-l border-border flex flex-col bg-card h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center justify-between gap-2">
          {/* Name + badges */}
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-[12px] font-semibold text-bright truncate">{agent.name}</span>
            {isBuiltin && (
              <span className="shrink-0 text-[8px] tracking-wider px-1.5 py-0.5 border border-amber/30 text-amber bg-amber/5 rounded">
                BUILTIN
              </span>
            )}
            <span className={`shrink-0 text-[8px] tracking-wider px-1.5 py-0.5 border rounded ${
              agent.is_active
                ? "border-green/30 text-green bg-green/5"
                : "border-border text-muted-foreground/40"
            }`}>
              {agent.is_active ? "ACTIVE" : "INACTIVE"}
            </span>
          </div>

          {/* Action icons */}
          <div className="flex items-center gap-1 shrink-0">
            {/* Clone */}
            <button onClick={() => clone()} disabled={cloning} title="Clone agent"
              className="p-1.5 rounded text-muted-foreground/50 hover:text-cyan hover:bg-cyan/10 hover:ring-1 hover:ring-cyan/40 transition-all disabled:opacity-40">
              {cloning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Copy className="w-3.5 h-3.5" />}
            </button>

            {/* Deactivate / Reactivate */}
            {agent.is_active ? (
              <button onClick={() => deactivate()} disabled={deactivating}
                title="Deactivate agent"
                className="p-1.5 rounded text-muted-foreground/50 hover:text-amber hover:bg-amber/10 hover:ring-1 hover:ring-amber/40 transition-all disabled:opacity-40">
                {deactivating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PowerOff className="w-3.5 h-3.5" />}
              </button>
            ) : (
              <button onClick={() => reactivate()} disabled={reactivating}
                title="Reactivate agent"
                className="p-1.5 rounded text-muted-foreground/50 hover:text-green hover:bg-green/10 hover:ring-1 hover:ring-green/40 transition-all disabled:opacity-40">
                {reactivating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Power className="w-3.5 h-3.5" />}
              </button>
            )}

            {/* Delete — custom agents only */}
            {!isBuiltin && (
              <button onClick={() => hardDelete()} disabled={deleting}
                title="Delete agent permanently"
                className="p-1.5 rounded text-muted-foreground/50 hover:text-red hover:bg-red/10 hover:ring-1 hover:ring-red/40 transition-all disabled:opacity-40">
                {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
              </button>
            )}

            {/* Divider + Close */}
            <div className="w-px h-4 bg-border mx-1" />
            <button onClick={onClose} className="p-1.5 rounded text-muted-foreground/50 hover:text-foreground hover:bg-accent hover:ring-1 hover:ring-border transition-all">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
        <div className="text-[10px] text-muted-foreground/40 mt-0.5">v{agent.version} · {agent.role}</div>
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-3">
        <div>
          <label className={lbl}>DESCRIPTION</label>
          <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
            className={inp} placeholder="What this agent does..." />
        </div>

        {/* ── System Prompt with TEMPLATE / PREVIEW tabs ── */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className={lbl}>SYSTEM PROMPT</label>
            <div className="flex gap-0.5 bg-muted/30 rounded p-0.5">
              {(["template", "preview"] as const).map((tab) => (
                <button key={tab} onClick={() => setPromptTab(tab)}
                  className={`px-2 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider transition-colors ${
                    promptTab === tab
                      ? "bg-border text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}>
                  {tab}
                </button>
              ))}
            </div>
          </div>

          {promptTab === "template" ? (
            <textarea value={form.system_prompt_template}
              onChange={(e) => setForm({ ...form, system_prompt_template: e.target.value })}
              rows={8} className={`${inp} font-mono text-[11px] resize-none leading-relaxed`} />
          ) : (
            <div className="rounded border border-border bg-muted/10 p-3 min-h-[130px] text-[11px] leading-relaxed font-mono whitespace-pre-wrap">
              <style>{`
                .var-known  { background: rgba(34,197,94,0.18); color: #86efac; border-radius: 3px; padding: 0 2px; font-style: italic; }
                .var-unknown { background: rgba(239,68,68,0.18); color: #fca5a5; border-radius: 3px; padding: 0 2px; font-style: italic; }
              `}</style>
              <span dangerouslySetInnerHTML={{ __html: previewHtml }} />
            </div>
          )}

          {/* Variable editor — shown only in preview tab */}
          {promptTab === "preview" && detectedVars.length > 0 && (
            <div className="mt-2 space-y-1">
              <p className="text-[9px] text-muted-foreground/50 uppercase tracking-widest mb-1">Preview values</p>
              {detectedVars.map((v) => {
                const isKnown = v === "task_description" || v === "job_context";
                return (
                  <div key={v} className="flex items-center gap-2">
                    <span className={`text-[9px] font-mono shrink-0 ${isKnown ? "text-green-400/70" : "text-red-400/70"}`}>
                      {`{{${v}}}`}
                    </span>
                    <input
                      value={previewVars[v] ?? ""}
                      onChange={(e) => setPreviewVars((prev) => ({ ...prev, [v]: e.target.value }))}
                      placeholder={isKnown ? "" : "unknown — define value"}
                      className={`${inp} text-[10px] py-0.5 h-6`}
                    />
                  </div>
                );
              })}
            </div>
          )}
          {promptTab === "template" && (
            <p className="text-[9px] text-muted-foreground/40 mt-1">
              Use {"{{variable}}"} to inject context at runtime
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={lbl}>PROVIDER</label>
            <select value={form.llm_provider}
              onChange={(e) => {
                const prov = e.target.value;
                const firstModel = PROVIDER_MODELS[prov]?.[0] ?? form.llm_model;
                setForm({ ...form, llm_provider: prov, llm_model: firstModel });
              }}
              className={inp}>
              {Object.keys(PROVIDER_MODELS).map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className={lbl}>MODEL</label>
            <ModelSelect provider={form.llm_provider} value={form.llm_model}
              onChange={(v) => setForm({ ...form, llm_model: v })} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={lbl}>MAX ITER</label>
            <input type="number" min={1} max={100} value={form.max_iterations}
              onChange={(e) => setForm({ ...form, max_iterations: +e.target.value })} className={inp} />
          </div>
          <div>
            <label className={lbl}>TIMEOUT (s)</label>
            <input type="number" min={10} max={600} value={form.timeout_seconds}
              onChange={(e) => setForm({ ...form, timeout_seconds: +e.target.value })} className={inp} />
          </div>
        </div>

        <div>
          <label className={lbl}>ALLOWED SYSCALLS</label>
          <div className="flex flex-wrap gap-1.5 p-3 border border-border bg-background">
            {tools.map((t) => (
              <button key={t.name} onClick={() => toggleTool(t.name)}
                className={`text-[10px] px-2 py-1 border font-mono transition-colors ${
                  allowedTools.includes(t.name)
                    ? "border-amber text-amber bg-amber/10"
                    : "border-border text-muted-foreground hover:border-muted-foreground"
                }`}>
                {t.name}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className={lbl}>OUTPUT SCHEMA</label>
          <OutputSchemaEditor fields={schemaFields} onChange={setSchemaFields} />
        </div>

        {/* Metadata */}
        <div className="border border-border bg-background p-3 space-y-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-muted-foreground/40">created</span>
            <span className="text-muted-foreground tabular">{new Date(agent.created_at).toLocaleDateString()}</span>
          </div>
          {agent.updated_at && (
            <div className="flex justify-between text-[10px]">
              <span className="text-muted-foreground/40">last updated</span>
              <span className="text-muted-foreground tabular">{new Date(agent.updated_at).toLocaleDateString()}</span>
            </div>
          )}
          <div className="flex justify-between text-[10px]">
            <span className="text-muted-foreground/40">status</span>
            <span className={agent.is_active ? "text-green" : "text-muted-foreground"}>
              {agent.is_active ? "active" : "inactive"}
            </span>
          </div>
        </div>
      </div>

      {/* Save + Export/Import */}
      <div className="px-4 py-3 border-t border-border shrink-0 space-y-2">
        <button onClick={() => save()} disabled={saving}
          className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs border disabled:opacity-40 transition-colors"
          style={saved
            ? { background: "rgba(143,181,160,0.1)", borderColor: "#8FB5A0", color: "#8FB5A0" }
            : { background: "rgba(201,168,76,0.08)", borderColor: "#C9A84C", color: "#C9A84C" }}>
          {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : saved ? "SAVED ✓" : "SAVE CHANGES"}
        </button>
        <div className="flex gap-2">
          <button onClick={exportJson}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-[10px] border border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors">
            <Download className="w-3 h-3" /> EXPORT JSON
          </button>
          <label className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-[10px] border border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors cursor-pointer">
            <Upload className="w-3 h-3" /> IMPORT JSON
            <input type="file" accept=".json,application/json" className="hidden" onChange={importJson} />
          </label>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function AgentRegistryPage() {
  const { data: agents = [], isLoading } = useAgents();
  const { data: tools = [] } = useTools();
  const [showRegister, setShowRegister] = useState(false);
  const [selected, setSelected] = useState<AgentDefinition | null>(null);

  function handleCloned(cloned: AgentDefinition) {
    setSelected(cloned);
  }

  return (
    <div className="flex flex-col h-full">
      {showRegister && <RegisterModal tools={tools} onClose={() => setShowRegister(false)} />}

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border shrink-0">
        <div>
          <div className="os-label mb-0.5">SERVICES / AGENT REGISTRY</div>
          <h1 className="text-[15px] font-semibold text-bright">Agent Definitions</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[12px] text-muted-foreground tabular">
            {agents.length} registered {isLoading && <Loader2 className="w-3 h-3 animate-spin inline ml-1" />}
          </span>
          <button onClick={() => setShowRegister(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] border border-border rounded-[var(--radius)] hover:border-[#C9A84C] hover:text-[#C9A84C] transition-colors">
            <Plus className="w-3.5 h-3.5" /> REGISTER
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Table */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Column headers */}
          <div className="grid grid-cols-[180px_80px_150px_100px_60px_60px_70px_20px] gap-3 px-5 py-2 text-[9px] tracking-[0.1em] text-muted-foreground/30 uppercase border-b border-border bg-card/50 shrink-0 select-none">
            <span>NAME</span><span>ROLE</span><span>MODEL</span><span>PROVIDER</span>
            <span>ITER</span><span>TOOLS</span><span>STATE</span><span />
          </div>

          <div className="flex-1 overflow-auto divide-y divide-border/50">
            {agents.map((agent) => (
              <button key={agent.name} onClick={() => setSelected(selected?.name === agent.name ? null : agent)}
                className={`w-full grid grid-cols-[180px_80px_150px_100px_60px_60px_70px_20px] gap-3 px-5 py-3 transition-colors items-center text-left ${
                  selected?.name === agent.name ? "bg-accent" : "hover:bg-accent/60"
                }`}>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-medium text-foreground">{agent.name}</span>
                    {BUILTIN_AGENTS.has(agent.name) && (
                      <span className="text-[8px] tracking-wider px-1.5 py-0.5 border border-amber/30 text-amber bg-amber/5 rounded shrink-0">
                        BUILTIN
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-muted-foreground/40">v{agent.version}</div>
                </div>
                <span className="text-[11px] px-2 py-0.5 border border-border rounded text-muted-foreground bg-background w-fit">
                  {agent.role}
                </span>
                <span className="text-[11px] font-mono truncate" style={{ color: "#C9A84C" }}>{agent.llm_model}</span>
                <span className="text-[11px] text-muted-foreground">{agent.llm_provider}</span>
                <span className="text-[11px] text-muted-foreground tabular">{agent.max_iterations}</span>
                <span className="text-[11px] text-muted-foreground tabular">{agent.allowed_tools.length}</span>
                <span className="flex items-center gap-1.5">
                  <span className={`dot ${agent.is_active ? "dot-running" : "dot-dim"}`} />
                  <span className={`text-[11px] ${agent.is_active ? "text-green" : "text-muted-foreground"}`}>
                    {agent.is_active ? "active" : "off"}
                  </span>
                </span>
                <ChevronRight className={`w-3.5 h-3.5 transition-transform ${selected?.name === agent.name ? "rotate-90 text-[#C9A84C]" : "text-muted-foreground/30"}`} />
              </button>
            ))}

            {agents.length === 0 && !isLoading && (
              <div className="flex items-center justify-center py-16 text-[12px] text-muted-foreground/30">
                no agents registered — click REGISTER to add one
              </div>
            )}
          </div>
        </div>

        {/* Edit panel */}
        {selected && (
          <EditPanel
            key={selected.name}
            agent={selected}
            tools={tools}
            onClose={() => setSelected(null)}
            onCloned={handleCloned}
          />
        )}
      </div>
    </div>
  );
}
