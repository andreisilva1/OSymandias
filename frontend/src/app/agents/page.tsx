"use client";

import { useState, useMemo } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useAgents, useTools } from "@/hooks/useJobData";
import { api } from "@/lib/api";
import { Plus, Loader2, X, Copy, Trash2, PowerOff, Power, Download, Upload, Search } from "lucide-react";
import type { AgentDefinition, ToolDefinition } from "@/types";

// ── constants ────────────────────────────────────────────────────────────────

const BUILTIN_NAMES = new Set(["PlannerAgent","ResearchAgent","WriterAgent","AnalystAgent","EvaluatorAgent"]);

const PROVIDER_MODELS: Record<string, string[]> = {
  ollama:    ["llama3.2"],
  openai:    ["gpt-4o","gpt-4o-mini","gpt-4-turbo","gpt-3.5-turbo","o1-mini","o1-preview"],
  anthropic: ["claude-sonnet-4-6","claude-opus-4-8","claude-haiku-4-5-20251001","claude-3-5-sonnet-20241022"],
  deepseek:  ["deepseek-chat","deepseek-coder","deepseek-reasoner"],
  groq:      ["llama-3.1-70b-versatile","llama-3.1-8b-instant","mixtral-8x7b-32768"],
  gemini:    ["gemini-1.5-pro","gemini-1.5-flash","gemini-2.0-flash-exp"],
};

const FRAMEWORK_META: Record<string, { label: string; color: string }> = {
  crewai:        { label: "CrewAI",       color: "#a07cdc" },
  langchain:     { label: "LangChain",    color: "#6fb896" },
  llamaindex:    { label: "LlamaIndex",   color: "#d47cb8" },
  smolagents:    { label: "smolagents",   color: "#d49c5b" },
  "openai-agents":{ label: "OAI Agents", color: "#5b8fd4" },
  autogen:       { label: "AutoGen",      color: "#5bbfd4" },
};

// accent color per agent
function accentFor(a: AgentDefinition): string {
  if (a.agent_kind === "external") {
    if (a.framework) return FRAMEWORK_META[a.framework]?.color ?? "#888";
    return "#666";
  }
  return "#c9a84c";
}

// ── tiny helpers ─────────────────────────────────────────────────────────────

const inp = "os-input";
const lbl = "os-label block mb-1.5";

function Badge({ children, color, bg, border }: { children: React.ReactNode; color: string; bg: string; border: string }) {
  return (
    <span className="text-[8px] tracking-wider px-1.5 py-0.5 border rounded shrink-0"
      style={{ color, background: bg, borderColor: border }}>
      {children}
    </span>
  );
}

function AgentBadge({ agent }: { agent: AgentDefinition }) {
  if (agent.agent_kind === "builtin")
    return <Badge color="#c9a84c" bg="rgba(201,168,76,.07)" border="rgba(201,168,76,.35)">BUILTIN</Badge>;
  if (agent.framework) {
    const fw = FRAMEWORK_META[agent.framework] ?? { label: agent.framework, color: "#888" };
    return <Badge color={fw.color} bg={`${fw.color}12`} border={`${fw.color}50`}>{fw.label}</Badge>;
  }
  return <Badge color="#777" bg="rgba(100,100,120,.07)" border="rgba(100,100,120,.3)">λ</Badge>;
}

function StripeClass(a: AgentDefinition): string {
  if (a.agent_kind === "builtin") return "row-builtin";
  if (a.framework && FRAMEWORK_META[a.framework]) return `row-fw`;
  return "row-ext";
}

// ── schema helpers ────────────────────────────────────────────────────────────

type SchemaField = { key: string; type: string; required: boolean };
const FIELD_TYPES = ["string","number","boolean","array","object"];

function schemaToFields(schema: Record<string,unknown> | undefined): SchemaField[] {
  if (!schema || typeof schema !== "object") return [];
  const props = (schema as any).properties ?? {};
  const req: string[] = (schema as any).required ?? [];
  return Object.entries(props).map(([key, def]: [string, any]) => {
    // direct type
    let type: string = def?.type;
    // Pydantic v2 Optional → anyOf: [{type: X}, {type: "null"}]
    if (!type && Array.isArray(def?.anyOf)) {
      const nonNull = def.anyOf.find((t: any) => t.type && t.type !== "null");
      type = nonNull?.type;
    }
    // $ref → object
    if (!type && def?.$ref) type = "object";
    // integer → number (for display bucketing)
    if (type === "integer") type = "number";
    return { key, type: type ?? "string", required: req.includes(key) };
  });
}

function fieldsToSchema(fields: SchemaField[]): Record<string,unknown> {
  const properties: Record<string,{type:string}> = {};
  const required: string[] = [];
  for (const f of fields) {
    if (!f.key.trim()) continue;
    properties[f.key.trim()] = { type: f.type };
    if (f.required) required.push(f.key.trim());
  }
  return { type: "object", properties, required };
}

function SchemaDisplay({ fields }: { fields: SchemaField[] }) {
  if (!fields.length)
    return <span className="text-[11px] text-muted-foreground/30">not defined</span>;
  return (
    <div className="space-y-1">
      {fields.map((f, i) => (
        <div key={i} className="flex items-center gap-2 px-3 py-1.5 border border-border bg-background rounded-[var(--radius)] text-[11px] min-w-0">
          <span className="font-mono text-bright shrink-0 max-w-[160px] truncate" title={f.key}>{f.key}</span>
          <span className="text-muted-foreground/40 shrink-0">{f.type}</span>
          <span className={`ml-auto shrink-0 text-[8px] px-1.5 py-0.5 border rounded ${f.required ? "border-amber/40 text-amber" : "border-border text-muted-foreground/50"}`}>
            {f.required ? "req" : "opt"}
          </span>
        </div>
      ))}
    </div>
  );
}

function SchemaEditor({ fields, onChange }: { fields: SchemaField[]; onChange: (f: SchemaField[]) => void }) {
  function update(i: number, patch: Partial<SchemaField>) {
    onChange(fields.map((f, idx) => idx === i ? { ...f, ...patch } : f));
  }
  return (
    <div className="space-y-1">
      {fields.map((f, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <input value={f.key} onChange={e => update(i, { key: e.target.value })}
            placeholder="field_name" className={`${inp} font-mono text-[10px] py-0.5 h-6 flex-1`} />
          <select value={f.type} onChange={e => update(i, { type: e.target.value })}
            className={`${inp} text-[10px] py-0.5 h-6 w-24`}>
            {FIELD_TYPES.map(t => <option key={t}>{t}</option>)}
          </select>
          <button onClick={() => update(i, { required: !f.required })}
            className={`text-[8px] px-1.5 h-6 border rounded transition-colors ${f.required ? "border-amber/60 text-amber bg-amber/10" : "border-border text-muted-foreground"}`}>
            REQ
          </button>
          <button onClick={() => onChange(fields.filter((_, idx) => idx !== i))}
            className="text-muted-foreground/40 hover:text-red transition-colors">
            <X className="w-3 h-3" />
          </button>
        </div>
      ))}
      <button onClick={() => onChange([...fields, { key: "", type: "string", required: false }])}
        className="flex items-center gap-1 text-[10px] text-muted-foreground/40 hover:text-muted-foreground transition-colors mt-0.5">
        <Plus className="w-3 h-3" /> add field
      </button>
    </div>
  );
}

// ── model select ──────────────────────────────────────────────────────────────

function ModelSelect({ provider, value, onChange }: { provider: string; value: string; onChange: (v: string) => void }) {
  const fallback = PROVIDER_MODELS[provider] ?? [];
  const { data: fetched, isLoading, isError } = useQuery({
    queryKey: ["provider-models", provider],
    queryFn: () => api.providers.models(provider),
    staleTime: 5 * 60 * 1000, retry: 1,
  });
  const models = (!isLoading && !isError && fetched?.length) ? fetched : fallback;
  return (
    <select value={models.includes(value) ? value : (models[0] ?? "")}
      onChange={e => onChange(e.target.value)} className={inp} disabled={isLoading}>
      {models.map(m => <option key={m} value={m}>{m}</option>)}
    </select>
  );
}

// ── register modal ────────────────────────────────────────────────────────────

function RegisterModal({ tools, onClose }: { tools: ToolDefinition[]; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "", role: "worker", description: "",
    system_prompt_template: "", llm_provider: "ollama", llm_model: "llama3.2",
    max_iterations: 10, timeout_seconds: 120, requires_approval: false,
  });
  const [allowedTools, setAllowedTools] = useState<string[]>([]);
  const [err, setErr] = useState("");

  const { mutate, isPending } = useMutation({
    mutationFn: () => api.agents.create({ ...form, allowed_tools: allowedTools }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["agents"] }); onClose(); },
    onError: (e: Error) => setErr(e.message),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div className="bg-card border border-border w-[540px] max-h-[90vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
          <span className="text-[9px] tracking-[.15em] text-muted-foreground/50 uppercase">REGISTER BUILTIN AGENT</span>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
        </div>
        <div className="overflow-auto flex-1 p-5 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={lbl}>NAME *</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className={inp} placeholder="MyAgent" />
            </div>
            <div>
              <label className={lbl}>ROLE</label>
              <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} className={inp}>
                {["worker","supervisor","researcher","writer","analyst","evaluator"].map(r => <option key={r}>{r}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className={lbl}>DESCRIPTION</label>
            <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className={inp} />
          </div>
          <div>
            <label className={lbl}>SYSTEM PROMPT *</label>
            <textarea value={form.system_prompt_template} onChange={e => setForm({ ...form, system_prompt_template: e.target.value })}
              rows={7} className={`${inp} font-mono text-xs resize-none leading-relaxed`}
              placeholder={"You are a {{role}} agent.\nTask: {{task_description}}\n\nOutput ONLY valid JSON."} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={lbl}>PROVIDER</label>
              <select value={form.llm_provider} onChange={e => setForm({ ...form, llm_provider: e.target.value, llm_model: PROVIDER_MODELS[e.target.value]?.[0] ?? "" })} className={inp}>
                {Object.keys(PROVIDER_MODELS).map(p => <option key={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className={lbl}>MODEL</label>
              <ModelSelect provider={form.llm_provider} value={form.llm_model} onChange={v => setForm({ ...form, llm_model: v })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={lbl}>MAX ITER</label>
              <input type="number" min={1} max={100} value={form.max_iterations} onChange={e => setForm({ ...form, max_iterations: +e.target.value })} className={inp} />
            </div>
            <div>
              <label className={lbl}>TIMEOUT (s)</label>
              <input type="number" min={10} max={600} value={form.timeout_seconds} onChange={e => setForm({ ...form, timeout_seconds: +e.target.value })} className={inp} />
            </div>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.requires_approval} onChange={e => setForm({ ...form, requires_approval: e.target.checked })} />
            <span className="text-[12px] text-foreground">Requires approval</span>
            <span className="text-[11px] text-muted-foreground/60">— tasks routed here wait in HUMAN_REVIEW</span>
          </label>
          <div>
            <label className={lbl}>TOOLS</label>
            <div className="flex flex-wrap gap-1.5 p-3 border border-border bg-background">
              {tools.map(t => (
                <button key={t.name} onClick={() => setAllowedTools(p => p.includes(t.name) ? p.filter(x => x !== t.name) : [...p, t.name])}
                  className={`text-[10px] px-2 py-1 border font-mono transition-colors ${allowedTools.includes(t.name) ? "border-amber text-amber bg-amber/10" : "border-border text-muted-foreground hover:border-muted-foreground"}`}>
                  {t.name}
                </button>
              ))}
            </div>
          </div>
          {err && <p className="text-[11px] text-red">{err}</p>}
        </div>
        <div className="flex justify-end gap-2 px-5 py-3 border-t border-border shrink-0">
          <button onClick={onClose} className="px-4 py-2 text-[12px] text-muted-foreground border border-border rounded-[var(--radius)] hover:bg-accent transition-colors">CANCEL</button>
          <button onClick={() => mutate()} disabled={isPending || !form.name.trim() || !form.system_prompt_template.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-[12px] border rounded-[var(--radius)] disabled:opacity-40 transition-colors"
            style={{ background: "rgba(201,168,76,.08)", borderColor: "#C9A84C", color: "#C9A84C" }}>
            {isPending && <Loader2 className="w-3 h-3 animate-spin" />} REGISTER
          </button>
        </div>
      </div>
    </div>
  );
}

// ── detail panel ──────────────────────────────────────────────────────────────

function DetailPanel({ agent, tools, onClose, onCloned }: {
  agent: AgentDefinition; tools: ToolDefinition[];
  onClose: () => void; onCloned: (a: AgentDefinition) => void;
}) {
  const qc = useQueryClient();
  const isExternal = agent.agent_kind === "external";
  const isBuiltin  = BUILTIN_NAMES.has(agent.name);
  const accent     = accentFor(agent);

  // form state — only used for builtin/LLM editing
  const [form, setForm] = useState({
    description:            agent.description ?? "",
    system_prompt_template: agent.system_prompt_template,
    llm_provider:           agent.llm_provider,
    llm_model:              agent.llm_model,
    max_iterations:         agent.max_iterations,
    timeout_seconds:        agent.timeout_seconds,
    requires_approval:      agent.requires_approval ?? false,
  });
  const [allowedTools, setAllowedTools] = useState<string[]>(agent.allowed_tools);
  const [outputFields, setOutputFields] = useState<SchemaField[]>(() =>
    schemaToFields(agent.output_schema as any)
  );
  const [saved, setSaved] = useState(false);
  const [promptTab, setPromptTab] = useState<"edit"|"preview">("edit");

  const { mutate: save, isPending: saving } = useMutation({
    mutationFn: () => api.agents.update(agent.name, {
      ...(isExternal ? {} : form),
      requires_approval: form.requires_approval,  // runtime policy — editable for any agent kind
      allowed_tools: isExternal ? undefined : allowedTools,
      output_schema: outputFields.length ? fieldsToSchema(outputFields) : undefined,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["agents"] }); setSaved(true); setTimeout(() => setSaved(false), 2000); },
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["agents"] });

  const { mutate: deactivate } = useMutation<void,Error,void>({
    mutationFn: () => api.agents.deactivate(agent.name),
    onSettled: () => { invalidate(); onClose(); },
  });
  const { mutate: reactivate } = useMutation<void,Error,void>({
    mutationFn: () => api.agents.reactivate(agent.name),
    onSettled: () => { invalidate(); onClose(); },
  });
  const { mutate: hardDelete } = useMutation<void,Error,void>({
    mutationFn: () => api.agents.delete(agent.name),
    onMutate: () => { qc.setQueryData<AgentDefinition[]>(["agents"], old => old?.filter(a => a.name !== agent.name) ?? []); onClose(); },
    onSettled: () => invalidate(),
  });
  const { mutate: clone, isPending: cloning } = useMutation({
    mutationFn: () => api.agents.clone(agent.name),
    onSuccess: async (cloned) => { await invalidate(); onCloned(cloned); },
  });

  function exportJson() {
    const blob = new Blob([JSON.stringify({ name: agent.name, ...form, allowed_tools: allowedTools, output_schema: outputFields.length ? fieldsToSchema(outputFields) : undefined }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `${agent.name}.json`; a.click();
    URL.revokeObjectURL(url);
  }

  function importJson(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    file.text().then(text => {
      try {
        const d = JSON.parse(text);
        setForm(f => ({ ...f, ...d }));
        if (Array.isArray(d.allowed_tools)) setAllowedTools(d.allowed_tools);
        if (d.output_schema) setOutputFields(schemaToFields(d.output_schema));
      } catch { /* ignore */ }
    });
    e.target.value = "";
  }

  // preview prompt
  const detectedVars = useMemo(() => {
    const m = [...form.system_prompt_template.matchAll(/\{\{(\w+)\}\}/g)];
    return [...new Set(m.map(x => x[1]))];
  }, [form.system_prompt_template]);
  const [previewVars, setPreviewVars] = useState<Record<string,string>>({
    task_description: "Research the top AI frameworks in 2025.",
    job_context: "Market Research · HIGH priority",
  });
  const previewHtml = useMemo(() => {
    let out = form.system_prompt_template.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
    out = out.replace(/\{\{(\w+)\}\}/g, (_,k) => {
      const v = previewVars[k];
      return v ? `<mark class="vk">${v}</mark>` : `<mark class="vu">{{${k}}}</mark>`;
    });
    return out.replace(/\n/g,"<br/>");
  }, [form.system_prompt_template, previewVars]);

  // callable ref display
  const callableModule = agent.callable_ref?.split(".").slice(0,-1).join(".") ?? "";
  const callableFn     = agent.callable_ref?.split(".").pop() ?? "";

  const fw = agent.framework ? FRAMEWORK_META[agent.framework] : null;

  return (
    <div className="w-[420px] shrink-0 border-l border-border flex flex-col bg-card h-full"
      style={{ borderTopColor: `${accent}30` }}>

      {/* header */}
      <div className="px-4 py-3 border-b flex-shrink-0" style={{ borderColor: `${accent}20` }}>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0 flex-wrap">
            <span className="text-[13px] font-semibold text-bright truncate">{agent.name}</span>
            <AgentBadge agent={agent} />
            <span className={`text-[8px] tracking-wider px-1.5 py-0.5 border rounded shrink-0 ${agent.is_active ? "border-green/30 text-green bg-green/5" : "border-border text-muted-foreground/40"}`}>
              {agent.is_active ? "ACTIVE" : "INACTIVE"}
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button onClick={() => clone()} disabled={cloning} title="Clone"
              className="p-1.5 rounded text-muted-foreground/50 hover:text-cyan hover:bg-cyan/10 transition-all disabled:opacity-40">
              {cloning ? <Loader2 className="w-3.5 h-3.5 animate-spin"/> : <Copy className="w-3.5 h-3.5"/>}
            </button>
            {agent.is_active
              ? <button onClick={() => deactivate()} title="Deactivate" className="p-1.5 rounded text-muted-foreground/50 hover:text-amber hover:bg-amber/10 transition-all"><PowerOff className="w-3.5 h-3.5"/></button>
              : <button onClick={() => reactivate()} title="Activate" className="p-1.5 rounded text-muted-foreground/50 hover:text-green hover:bg-green/10 transition-all"><Power className="w-3.5 h-3.5"/></button>
            }
            {!isBuiltin && (
              <button onClick={() => hardDelete()} title="Delete" className="p-1.5 rounded text-muted-foreground/50 hover:text-red hover:bg-red/10 transition-all"><Trash2 className="w-3.5 h-3.5"/></button>
            )}
            <div className="w-px h-4 bg-border mx-0.5"/>
            <button onClick={onClose} className="p-1.5 rounded text-muted-foreground/50 hover:text-foreground hover:bg-accent transition-all"><X className="w-3.5 h-3.5"/></button>
          </div>
        </div>
        <div className="text-[10px] text-muted-foreground/40 mt-1">v{agent.version} · {agent.role}</div>
      </div>

      {/* body */}
      <div className="flex-1 overflow-auto p-4 space-y-4">

        {/* description */}
        {(agent.description || isExternal) && (
          <div>
            {isExternal
              ? <p className="text-[12px] text-muted-foreground leading-relaxed">{agent.description || <span className="opacity-30">no description</span>}</p>
              : <div>
                  <label className={lbl}>DESCRIPTION</label>
                  <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className={inp} />
                </div>
            }
          </div>
        )}

        {/* callable ref — external agents */}
        {agent.callable_ref && (
          <div>
            <label className={lbl}>CALLABLE REFERENCE</label>
            <div className="px-3 py-2.5 border border-border bg-background rounded-[var(--radius)] font-mono text-[11px]">
              <span className="text-muted-foreground/40">{callableModule}.</span>
              <span style={{ color: accent }}>{callableFn}</span>
            </div>
            <p className="text-[9px] text-muted-foreground/30 mt-1">
              auto-discovered via <code className="text-muted-foreground/50">osymandias.toml</code>
            </p>
          </div>
        )}

        {/* framework info */}
        {fw && (
          <div className="flex items-center gap-2 px-3 py-2 border rounded-[var(--radius)] text-[11px]"
            style={{ borderColor: `${fw.color}30`, background: `${fw.color}08` }}>
            <span className="font-medium" style={{ color: fw.color }}>{fw.label}</span>
            <span className="text-muted-foreground/40">·</span>
            <span className="text-muted-foreground/50">managed by your code</span>
          </div>
        )}

        {/* LLM config — builtin or external with explicit provider */}
        {(agent.llm_provider || agent.llm_model) && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={lbl}>PROVIDER</label>
              {isExternal
                ? <div className="px-3 py-2 border border-border bg-background rounded-[var(--radius)] text-[11px] text-muted-foreground font-mono">{agent.llm_provider}</div>
                : <select value={form.llm_provider} onChange={e => setForm({ ...form, llm_provider: e.target.value, llm_model: PROVIDER_MODELS[e.target.value]?.[0] ?? form.llm_model })} className={inp}>
                    {Object.keys(PROVIDER_MODELS).map(p => <option key={p}>{p}</option>)}
                  </select>
              }
            </div>
            <div>
              <label className={lbl}>MODEL</label>
              {isExternal
                ? <div className="px-3 py-2 border border-border bg-background rounded-[var(--radius)] text-[11px] font-mono" style={{ color: accent }}>{agent.llm_model}</div>
                : <ModelSelect provider={form.llm_provider} value={form.llm_model} onChange={v => setForm({ ...form, llm_model: v })} />
              }
            </div>
          </div>
        )}

        {/* iter + timeout — builtin only */}
        {!isExternal && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={lbl}>MAX ITER</label>
              <input type="number" min={1} max={100} value={form.max_iterations} onChange={e => setForm({ ...form, max_iterations: +e.target.value })} className={inp} />
            </div>
            <div>
              <label className={lbl}>TIMEOUT (s)</label>
              <input type="number" min={10} max={600} value={form.timeout_seconds} onChange={e => setForm({ ...form, timeout_seconds: +e.target.value })} className={inp} />
            </div>
          </div>
        )}

        {/* requires approval — any agent kind */}
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={form.requires_approval} onChange={e => setForm({ ...form, requires_approval: e.target.checked })} />
          <span className="text-[12px] text-foreground">Requires approval</span>
          <span className="text-[11px] text-muted-foreground/60">— tasks routed here wait in HUMAN_REVIEW</span>
        </label>

        {/* system prompt — builtin only */}
        {!isExternal && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className={lbl}>SYSTEM PROMPT</label>
              <div className="flex gap-0.5 bg-muted/20 rounded p-0.5">
                {(["edit","preview"] as const).map(tab => (
                  <button key={tab} onClick={() => setPromptTab(tab)}
                    className={`px-2 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider transition-colors ${promptTab===tab ? "bg-border text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
                    {tab}
                  </button>
                ))}
              </div>
            </div>
            {promptTab === "edit"
              ? <textarea value={form.system_prompt_template} onChange={e => setForm({ ...form, system_prompt_template: e.target.value })}
                  rows={8} className={`${inp} font-mono text-[10px] resize-none leading-relaxed`} />
              : <div className="border border-border bg-muted/10 rounded-[var(--radius)] p-3 min-h-[120px] text-[10px] font-mono leading-relaxed whitespace-pre-wrap">
                  <style>{`.vk{background:rgba(34,197,94,.15);color:#86efac;border-radius:2px;padding:0 2px}.vu{background:rgba(239,68,68,.15);color:#fca5a5;border-radius:2px;padding:0 2px}`}</style>
                  <span dangerouslySetInnerHTML={{ __html: previewHtml }} />
                  {detectedVars.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-border space-y-1">
                      {detectedVars.map(v => (
                        <div key={v} className="flex items-center gap-2">
                          <span className="text-[9px] font-mono text-muted-foreground/50 shrink-0">{`{{${v}}}`}</span>
                          <input value={previewVars[v] ?? ""} onChange={e => setPreviewVars(p => ({ ...p, [v]: e.target.value }))}
                            className={`${inp} text-[10px] py-0.5 h-5`} />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
            }
          </div>
        )}

        {/* tools — builtin only */}
        {!isExternal && (
          <div>
            <label className={lbl}>TOOLS</label>
            <div className="flex flex-wrap gap-1.5 p-3 border border-border bg-background">
              {tools.map(t => (
                <button key={t.name} onClick={() => setAllowedTools(p => p.includes(t.name) ? p.filter(x => x !== t.name) : [...p, t.name])}
                  className={`text-[10px] px-2 py-1 border font-mono transition-colors ${allowedTools.includes(t.name) ? "border-amber text-amber bg-amber/10" : "border-border text-muted-foreground hover:border-muted-foreground"}`}>
                  {t.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* declared tools — external with tools set */}
        {isExternal && agent.allowed_tools.length > 0 && (
          <div>
            <label className={lbl}>DECLARED TOOLS</label>
            <div className="flex flex-wrap gap-1.5">
              {agent.allowed_tools.map(t => (
                <span key={t} className="text-[10px] px-2 py-1 border border-border font-mono text-muted-foreground bg-background rounded">
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* output schema */}
        <div>
          <label className={lbl}>OUTPUT SCHEMA</label>
          {isExternal
            ? <SchemaDisplay fields={outputFields} />
            : <SchemaEditor fields={outputFields} onChange={setOutputFields} />
          }
        </div>

        {/* timestamps */}
        <div className="grid grid-cols-2 gap-px border border-border overflow-hidden rounded-[var(--radius)]">
          {[
            ["created", new Date(agent.created_at).toLocaleDateString()],
            ["updated", agent.updated_at ? new Date(agent.updated_at).toLocaleDateString() : "—"],
          ].map(([k, v]) => (
            <div key={k} className="bg-background px-3 py-2">
              <div className="text-[9px] text-muted-foreground/40 uppercase tracking-wider">{k}</div>
              <div className="text-[11px] text-muted-foreground mt-0.5 tabular-nums">{v}</div>
            </div>
          ))}
        </div>
      </div>

      {/* footer */}
      <div className="px-4 py-3 border-t border-border shrink-0 space-y-2">
        <button onClick={() => save()} disabled={saving}
          className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs border disabled:opacity-40 transition-colors"
          style={saved
            ? { background: "rgba(111,184,150,.1)", borderColor: "#6fb896", color: "#6fb896" }
            : { background: "rgba(201,168,76,.07)", borderColor: "#C9A84C", color: "#C9A84C" }}>
          {saving ? <Loader2 className="w-3 h-3 animate-spin"/> : saved ? "SAVED ✓" : "SAVE CHANGES"}
        </button>
        {!isExternal && (
          <div className="flex gap-2">
            <button onClick={exportJson} className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-[10px] border border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors">
              <Download className="w-3 h-3"/> EXPORT
            </button>
            <label className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-[10px] border border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors cursor-pointer">
              <Upload className="w-3 h-3"/> IMPORT
              <input type="file" accept=".json" className="hidden" onChange={importJson}/>
            </label>
          </div>
        )}
      </div>
    </div>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────

type FilterKind = "all" | "builtin" | "external";

export default function AgentRegistryPage() {
  const { data: agents = [], isLoading } = useAgents();
  const { data: tools  = [] } = useTools();
  const [showRegister, setShowRegister] = useState(false);
  const [selected, setSelected]         = useState<AgentDefinition | null>(null);
  const [filter, setFilter]             = useState<FilterKind>("all");
  const [search, setSearch]             = useState("");

  const visible = useMemo(() => agents.filter(a => {
    if (filter === "builtin"  && a.agent_kind !== "builtin")  return false;
    if (filter === "external" && a.agent_kind !== "external") return false;
    if (search && !a.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  }), [agents, filter, search]);

  const pills: { label: string; value: FilterKind }[] = [
    { label: "ALL",      value: "all"      },
    { label: "BUILTIN",  value: "builtin"  },
    { label: "EXTERNAL", value: "external" },
  ];

  return (
    <div className="flex flex-col h-full">
      {showRegister && <RegisterModal tools={tools} onClose={() => setShowRegister(false)} />}

      {/* header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border shrink-0">
        <div>
          <div className="os-label mb-0.5">SERVICES / AGENT REGISTRY</div>
          <h1 className="text-[15px] font-semibold text-bright">Agent Definitions</h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <span className="tabular"><span className="text-bright font-medium">{agents.filter(a=>a.is_active).length}</span> active</span>
            <span className="text-muted-foreground/30">·</span>
            <span className="tabular"><span className="text-bright font-medium">{agents.length}</span> total</span>
            {isLoading && <Loader2 className="w-3 h-3 animate-spin ml-1"/>}
          </div>
          <button onClick={() => setShowRegister(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] border rounded-[var(--radius)] transition-colors"
            style={{ borderColor: "rgba(201,168,76,.4)", color: "#C9A84C", background: "rgba(201,168,76,.06)" }}>
            <Plus className="w-3.5 h-3.5"/> REGISTER
          </button>
        </div>
      </div>

      {/* toolbar */}
      <div className="flex items-center gap-3 px-5 py-2.5 border-b border-border bg-card/50 shrink-0">
        <div className="flex items-center gap-2 flex-1 max-w-[260px] px-3 py-1.5 border border-border bg-background rounded-[var(--radius)]">
          <Search className="w-3.5 h-3.5 text-muted-foreground/40 shrink-0"/>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="filter agents…" className="bg-transparent border-none outline-none text-[12px] text-foreground placeholder:text-muted-foreground/30 flex-1 min-w-0"/>
        </div>
        <div className="flex gap-1.5">
          {pills.map(p => (
            <button key={p.value} onClick={() => setFilter(p.value)}
              className={`px-3 py-1 text-[9px] tracking-wider border rounded-full transition-colors ${filter===p.value ? "border-amber/50 text-amber bg-amber/07" : "border-border text-muted-foreground hover:border-muted-foreground"}`}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* col headers */}
          <div className="grid grid-cols-[1fr_80px_160px_110px_50px_90px_18px] gap-3 px-5 py-2 text-[9px] tracking-[.1em] text-muted-foreground/30 uppercase border-b border-border bg-card/50 shrink-0 select-none">
            <span>NAME</span><span>ROLE</span><span>RUNTIME</span>
            <span>PROVIDER</span><span>ITER</span><span>STATUS</span><span/>
          </div>

          <div className="flex-1 overflow-auto divide-y divide-border/40">
            {visible.map(agent => {
              const isExt    = agent.agent_kind === "external";
              const accent   = accentFor(agent);
              const isSel    = selected?.name === agent.name;
              const fw       = agent.framework ? FRAMEWORK_META[agent.framework] : null;
              const runtime  = isExt ? (agent.llm_model || "python callable") : agent.llm_model;
              const provider = isExt ? (agent.llm_provider || "—") : agent.llm_provider;

              return (
                <button key={agent.name}
                  onClick={() => setSelected(isSel ? null : agent)}
                  className={`w-full grid grid-cols-[1fr_80px_160px_110px_50px_90px_18px] gap-3 px-5 py-3 transition-colors items-center text-left relative ${isSel ? "bg-accent" : "hover:bg-accent/50"}`}>
                  {/* left accent stripe */}
                  <span className="absolute left-0 top-0 bottom-0 w-0.5 transition-opacity"
                    style={{ background: accent, opacity: isSel ? 1 : 0 }}/>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-medium text-foreground">{agent.name}</span>
                      <AgentBadge agent={agent}/>
                    </div>
                    <div className="text-[10px] text-muted-foreground/40 mt-0.5">v{agent.version}</div>
                  </div>

                  <span className="text-[10px] px-2 py-0.5 border border-border text-muted-foreground bg-background rounded w-fit whitespace-nowrap">
                    {agent.role}
                  </span>

                  <span className="text-[11px] font-mono truncate"
                    style={{ color: isExt && !agent.llm_model ? "var(--muted-foreground)" : accent }}>
                    {runtime}
                  </span>

                  <span className="text-[11px] text-muted-foreground truncate">
                    {fw ? <span style={{ color: fw.color }}>{fw.label}</span> : provider}
                  </span>

                  <span className="text-[11px] text-muted-foreground/50 text-center">
                    {isExt ? "—" : agent.max_iterations}
                  </span>

                  <div className="flex items-center gap-1.5">
                    <span className={`w-1.5 h-1.5 rounded-full ${agent.is_active ? "bg-green shadow-[0_0_4px_var(--tw-shadow-color)]" : "bg-muted"}`}
                      style={agent.is_active ? { "--tw-shadow-color": "#6fb896" } as any : {}}/>
                    <span className={`text-[11px] ${agent.is_active ? "text-green" : "text-muted-foreground/40"}`}>
                      {agent.is_active ? "active" : "off"}
                    </span>
                  </div>

                  <span className={`text-[11px] transition-transform ${isSel ? "rotate-90 text-amber" : "text-muted-foreground/30"}`}>›</span>
                </button>
              );
            })}

            {visible.length === 0 && !isLoading && (
              <div className="flex flex-col items-center justify-center py-20 gap-2 text-[12px] text-muted-foreground/30">
                <span className="text-2xl opacity-20">⊘</span>
                no agents match
              </div>
            )}
          </div>
        </div>

        {selected && (
          <DetailPanel key={selected.name} agent={selected} tools={tools}
            onClose={() => setSelected(null)} onCloned={a => setSelected(a)}/>
        )}
      </div>
    </div>
  );
}
