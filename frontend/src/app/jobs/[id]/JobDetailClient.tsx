"use client";

import { useState, useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useJob, useJobTasks, useJobToolCalls, useJobMessages, useJobAgentInstances, useJobCostBreakdown, useTaskTrace } from "@/hooks/useJobData";
import { useJobStream } from "@/hooks/useJobStream";
import { StatusBadge } from "@/components/jobs/JobStatusBadge";
import { ExecutionTimeline } from "@/components/execution/ExecutionTimeline";
import { AgentGraph } from "@/components/execution/AgentGraph";
import { formatCost, formatTokens, formatDuration } from "@/lib/utils";
import { Clock, Cpu, DollarSign, Zap, Loader2, RotateCcw, Check } from "lucide-react";
import { JobOutputViewer } from "@/components/jobs/JobOutputViewer";
import { api } from "@/lib/api";

type Tab = "OVERVIEW" | "TIMELINE" | "CALL_GRAPH" | "COST" | "TRACE" | "EVENT_LOG" | "SYSCALLS" | "OUTPUT";
const TABS: Tab[] = ["OVERVIEW", "TIMELINE", "CALL_GRAPH", "COST", "TRACE", "EVENT_LOG", "SYSCALLS", "OUTPUT"];

const EV_COLOR: Record<string, string> = {
  JOB_CREATED:"text-cyan", JOB_STARTED:"text-cyan", JOB_COMPLETED:"text-green", JOB_FAILED:"text-red",
  TASK_STARTED:"text-blue", TASK_CREATED:"text-cyan", TASK_COMPLETED:"text-green", TASK_FAILED:"text-red", TASK_PROGRESS:"text-amber",
  AGENT_STARTED:"text-purple", AGENT_ITERATION:"text-muted-foreground", AGENT_COMPLETED:"text-green", AGENT_CRASHED:"text-red",
  TOOL_CALLED:"text-amber", TOOL_SUCCEEDED:"text-green", TOOL_FAILED:"text-red",
};

const TC_COLOR: Record<string, string> = {
  SUCCESS:"text-green", FAILED:"text-red", RUNNING:"text-cyan", PENDING:"text-amber", TIMEOUT:"text-red",
};

export function JobDetailClient({ id: staticId }: { id: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const id = pathname?.split("/")[2] || staticId;
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("OVERVIEW");
  const [resubmitting, setResubmitting] = useState(false);
  const [approving, setApproving] = useState<string | null>(null);
  const [traceTaskId, setTraceTaskId] = useState<string | null>(null);
  const { data: job, isLoading } = useJob(id);
  const { data: tasks = [] } = useJobTasks(id);
  const { data: toolCalls = [] } = useJobToolCalls(id);
  const { data: messages = [] } = useJobMessages(id);
  const { data: agentInstances = [] } = useJobAgentInstances(id);
  const { data: costBreakdown } = useJobCostBreakdown(id);
  const { data: trace, isLoading: traceLoading } = useTaskTrace(id, traceTaskId);
  const { events } = useJobStream(id);

  const isTerminal = job ? ["COMPLETED", "FAILED", "CANCELLED", "BUDGET_EXCEEDED"].includes(job.status) : false;

  const liveProgress = useMemo(() => {
    if (isTerminal) return {};
    const taskById = Object.fromEntries(tasks.map((t) => [t.id, t.title]));
    const seen = new Set<string>();
    const result: Record<string, unknown> = {};
    for (const ev of events) {
      if (ev.event_type === "TASK_PROGRESS" && ev.task_id && !seen.has(ev.task_id)) {
        seen.add(ev.task_id);
        const title = taskById[ev.task_id] ?? ev.task_id;
        result[title] = ev.payload;
      }
    }
    return result;
  }, [events, tasks, isTerminal]);

  if (isLoading || !job) {
    return (
      <div className="flex items-center justify-center h-full gap-2 text-muted-foreground text-[13px]">
        <Loader2 className="w-4 h-4 animate-spin" /> loading process…
      </div>
    );
  }

  const duration =
    job.started_at && job.completed_at
      ? new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()
      : job.started_at
      ? Date.now() - new Date(job.started_at).getTime()
      : undefined;

  async function handleResubmit() {
    setResubmitting(true);
    try {
      const newJob = await api.jobs.resubmit(id);
      router.push(`/jobs/${newJob.id}`);
    } catch (e) {
      console.error("Resubmit failed", e);
    } finally {
      setResubmitting(false);
    }
  }

  async function handleApprove(taskId: string) {
    setApproving(taskId);
    try {
      await api.jobs.approveTask(id, taskId);
      qc.invalidateQueries({ queryKey: ["job-tasks", id] });
      qc.invalidateQueries({ queryKey: ["job", id] });
    } catch (e) {
      console.error("Approve failed", e);
    } finally {
      setApproving(null);
    }
  }


  return (
    <div className="flex flex-col h-full">
      {/* Process header */}
      <div className="px-5 py-4 border-b border-border shrink-0">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3 mb-1.5">
              <span className="pid">{job.id.slice(0, 8)}</span>
              <StatusBadge status={job.status} />
              <span className="text-[11px] px-2 py-0.5 border border-border rounded-[var(--radius)] text-muted-foreground">{job.priority}</span>
            </div>
            <h1 className="text-[16px] font-semibold text-bright truncate">{job.title}</h1>
            {job.description && (
              <p className="text-[12px] text-muted-foreground mt-1 truncate">{job.description}</p>
            )}
          </div>
          {isTerminal && (
            <button
              onClick={handleResubmit}
              disabled={resubmitting}
              className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-[11px] border border-border rounded-[var(--radius)] text-muted-foreground hover:text-foreground hover:border-foreground/40 transition-colors disabled:opacity-50"
            >
              {resubmitting
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <RotateCcw className="w-3.5 h-3.5" />}
              resubmit
            </button>
          )}
        </div>

        {/* KPI strip */}
        <div className="flex items-center gap-6 mt-3.5 text-[11px]">
          {[
            { icon: Clock,      label: "runtime",  value: formatDuration(duration) },
            { icon: Cpu,        label: "tokens",   value: job.max_tokens ? `${formatTokens(job.total_tokens)} / ${formatTokens(job.max_tokens)}` : formatTokens(job.total_tokens) },
            { icon: DollarSign, label: "cost",     value: formatCost(job.estimated_cost) },
            { icon: Zap,        label: "tasks",    value: `${tasks.filter(t => t.status === "COMPLETED").length}/${tasks.length}` },
          ].map(({ icon: Icon, label, value }) => (
            <div key={label} className="flex items-center gap-1.5 text-muted-foreground">
              <Icon className="w-3.5 h-3.5" />
              <span className="os-label">{label}</span>
              <span className="text-foreground tabular font-mono">{value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex items-center border-b border-border px-5 shrink-0 bg-card/50">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-3 py-2.5 text-[11px] tracking-wide border-b-2 transition-colors -mb-px ${
              tab === t
                ? "text-foreground border-[#C9A84C]"
                : "text-muted-foreground border-transparent hover:text-foreground"
            }`}>
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto">

        {/* OVERVIEW */}
        {tab === "OVERVIEW" && (
          <div className="grid grid-cols-2 gap-4 p-5">
            <div className="space-y-4">
              {/* Process info */}
              <div>
                <div className="os-label mb-2">PROCESS INFO</div>
                <div className="border border-border bg-card rounded-[var(--radius)] p-3.5 space-y-2.5">
                  <div className="flex items-start gap-3">
                    <span className="os-label w-20 shrink-0 pt-px">description</span>
                    <span className="text-[12px] text-foreground leading-relaxed">
                      {job.description || <span className="text-muted-foreground/30 italic">none</span>}
                    </span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="os-label w-20 shrink-0 pt-px">created</span>
                    <span className="text-[12px] text-muted-foreground tabular font-mono">
                      {new Date(job.created_at).toLocaleString()}
                    </span>
                  </div>
                  {job.started_at && (
                    <div className="flex items-start gap-3">
                      <span className="os-label w-20 shrink-0 pt-px">started</span>
                      <span className="text-[12px] text-muted-foreground tabular font-mono">
                        {new Date(job.started_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                  {job.completed_at && (
                    <div className="flex items-start gap-3">
                      <span className="os-label w-20 shrink-0 pt-px">completed</span>
                      <span className="text-[12px] text-muted-foreground tabular font-mono">
                        {new Date(job.completed_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Task queue */}
              <div>
                <div className="os-label mb-2">
                  TASK QUEUE <span className="text-muted-foreground/30 normal-case tracking-normal ml-1">{tasks.length} tasks</span>
                </div>
                <div className="space-y-1.5">
                  {tasks.map((task) => (
                    <div key={task.id}
                      className="flex items-center justify-between p-3 border border-border bg-card rounded-[var(--radius)] hover:bg-accent transition-colors">
                      <div className="min-w-0 flex-1">
                        <div className="text-[12px] text-foreground truncate">{task.title}</div>
                        <div className="text-[11px] text-muted-foreground/50 mt-0.5">
                          {task.agent_type ?? "—"}
                          {task.attempt_count > 0 && <span className="ml-2 text-amber">attempt {task.attempt_count}/{task.max_attempts}</span>}
                        </div>
                      </div>
                      <div className="ml-3 shrink-0 flex items-center gap-2">
                        {task.status === "HUMAN_REVIEW" && (
                          <button
                            onClick={() => handleApprove(task.id)}
                            disabled={approving === task.id}
                            className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium border border-[#C9A84C]/50 text-[#C9A84C] rounded-[var(--radius)] hover:bg-[#C9A84C]/10 transition-colors disabled:opacity-50"
                          >
                            {approving === task.id
                              ? <Loader2 className="w-3 h-3 animate-spin" />
                              : <Check className="w-3 h-3" />}
                            approve
                          </button>
                        )}
                        <StatusBadge status={task.status} />
                      </div>
                    </div>
                  ))}
                  {tasks.length === 0 && (
                    <div className="text-[12px] text-muted-foreground/30 py-5 text-center border border-border rounded-[var(--radius)]">
                      no tasks spawned yet
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {/* Input payload */}
              <div>
                <div className="os-label mb-2">INPUT PAYLOAD</div>
                <pre className="text-[12px] bg-background border border-border rounded-[var(--radius)] p-3.5 overflow-auto max-h-48 leading-relaxed font-mono text-muted-foreground">
                  {Object.keys(job.input_payload ?? {}).length === 0
                    ? <span className="text-muted-foreground/30 italic">{"// empty — description field carries the prompt"}</span>
                    : JSON.stringify(job.input_payload, null, 2)}
                </pre>
              </div>

              {/* Retry policy */}
              <div>
                <div className="os-label mb-2">RETRY POLICY</div>
                <pre className="text-[12px] bg-background border border-border rounded-[var(--radius)] p-3.5 overflow-auto max-h-32 leading-relaxed font-mono text-muted-foreground">
                  {JSON.stringify(job.retry_policy, null, 2)}
                </pre>
              </div>

              {/* Task contexts */}
              {tasks.length > 0 && (
                <div>
                  <div className="os-label mb-2">TASK CONTEXTS</div>
                  <div className="space-y-1.5">
                    {tasks.map((task) => (
                      <details key={task.id} className="border border-border bg-card rounded-[var(--radius)] group">
                        <summary className="flex items-center justify-between px-3 py-2.5 cursor-pointer list-none hover:bg-accent transition-colors rounded-[var(--radius)]">
                          <span className="text-[12px] text-foreground truncate">{task.title}</span>
                          <span className="text-[10px] text-muted-foreground/30 ml-2 group-open:rotate-90 transition-transform">▶</span>
                        </summary>
                        <pre className="text-[11px] text-muted-foreground/70 px-3.5 pb-3.5 overflow-auto max-h-40 font-mono leading-relaxed border-t border-border/50">
                          {JSON.stringify(task.input_context, null, 2)}
                        </pre>
                      </details>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TIMELINE */}
        {tab === "TIMELINE" && (
          <div className="p-5">
            <ExecutionTimeline tasks={tasks} jobStartedAt={job.started_at} />
          </div>
        )}

        {/* CALL_GRAPH */}
        {tab === "CALL_GRAPH" && (
          <div className="p-5 h-[500px]">
            <AgentGraph instances={agentInstances} messages={messages} />
          </div>
        )}

        {/* COST */}
        {tab === "COST" && (
          <div className="p-5 grid grid-cols-2 gap-4">
            <div>
              <div className="os-label mb-2">
                BY AGENT <span className="text-muted-foreground/30 normal-case tracking-normal ml-1">{costBreakdown?.total_tokens ?? 0} tokens total</span>
              </div>
              <div className="border border-border bg-card rounded-[var(--radius)] divide-y divide-border/40">
                {(costBreakdown?.by_agent ?? []).map((a) => (
                  <div key={a.agent} className="flex items-center justify-between px-3.5 py-2.5">
                    <span className="text-[12px] text-foreground">{a.agent}</span>
                    <span className="text-[11px] text-muted-foreground font-mono tabular">
                      {formatTokens(a.tokens)} · {formatCost(a.cost)} · {a.instances}×
                    </span>
                  </div>
                ))}
                {(costBreakdown?.by_agent?.length ?? 0) === 0 && (
                  <div className="px-3.5 py-5 text-[12px] text-muted-foreground/30 text-center">no agent activity</div>
                )}
              </div>
            </div>
            <div>
              <div className="os-label mb-2">
                BY TOOL <span className="text-muted-foreground/30 normal-case tracking-normal ml-1">{formatCost(costBreakdown?.total_cost ?? 0)} total</span>
              </div>
              <div className="border border-border bg-card rounded-[var(--radius)] divide-y divide-border/40">
                {(costBreakdown?.by_tool ?? []).map((t) => (
                  <div key={t.tool} className="flex items-center justify-between px-3.5 py-2.5">
                    <span className="text-[12px] text-amber font-mono">{t.tool}</span>
                    <span className="text-[11px] text-muted-foreground font-mono tabular">{t.calls} calls · {formatCost(t.cost)}</span>
                  </div>
                ))}
                {(costBreakdown?.by_tool?.length ?? 0) === 0 && (
                  <div className="px-3.5 py-5 text-[12px] text-muted-foreground/30 text-center">no tool calls</div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TRACE */}
        {tab === "TRACE" && (
          <div className="p-5 space-y-4">
            <div className="flex items-center gap-3">
              <span className="os-label">TASK</span>
              <select
                className="filter-select"
                value={traceTaskId ?? ""}
                onChange={(e) => setTraceTaskId(e.target.value || null)}
              >
                <option value="">select a task…</option>
                {tasks.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
              </select>
            </div>

            {!traceTaskId && <div className="text-[12px] text-muted-foreground/30 py-8 text-center">pick a task to inspect its reasoning chain</div>}
            {traceTaskId && traceLoading && <div className="flex items-center gap-2 text-[12px] text-muted-foreground py-8 justify-center"><Loader2 className="w-4 h-4 animate-spin" /> loading trace…</div>}

            {trace && !traceLoading && (
              <div className="space-y-4">
                {/* Conversation — the reasoning chain */}
                <div>
                  <div className="os-label mb-2">CONVERSATION <span className="text-muted-foreground/30 normal-case tracking-normal ml-1">{trace.conversation.length} messages</span></div>
                  <div className="space-y-1.5">
                    {trace.conversation.map((m, i) => (
                      <div key={i} className="border border-border bg-card rounded-[var(--radius)] p-3">
                        <div className="os-label mb-1" style={{ color: m.role === "assistant" ? "#C9A84C" : m.role === "tool" ? "#60A890" : "#607080" }}>{m.role}</div>
                        <pre className="text-[11px] text-muted-foreground/80 whitespace-pre-wrap font-mono leading-relaxed overflow-auto max-h-48">
                          {m.content ? String(m.content) : (m.tool_calls ? JSON.stringify(m.tool_calls, null, 2) : <span className="text-muted-foreground/30">—</span>)}
                        </pre>
                      </div>
                    ))}
                    {trace.conversation.length === 0 && <div className="text-[12px] text-muted-foreground/30 py-5 text-center border border-border rounded-[var(--radius)]">no conversation recorded</div>}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* EVENT_LOG */}
        {tab === "EVENT_LOG" && (
          <div className="divide-y divide-border/30">
            <div className="grid grid-cols-[110px_160px_1fr_60px] gap-3 px-5 py-2 os-label bg-background/95 sticky top-0 select-none">
              <span>TIME</span><span>EVENT TYPE</span><span>DETAIL</span><span>DUR</span>
            </div>
            {events.length === 0 ? (
              <div className="flex items-center justify-center py-12 text-[12px] text-muted-foreground/30">
                no events yet
              </div>
            ) : (
              events.map((ev) => {
                const ts = new Date(ev.timestamp);
                const t = `${String(ts.getHours()).padStart(2,"0")}:${String(ts.getMinutes()).padStart(2,"0")}:${String(ts.getSeconds()).padStart(2,"0")}`;
                const c = EV_COLOR[ev.event_type] ?? "text-muted-foreground";
                return (
                  <div key={ev.id} className="grid grid-cols-[110px_160px_1fr_60px] gap-3 px-5 py-2 hover:bg-accent/40 items-center event-row-enter">
                    <span className="text-[11px] text-muted-foreground/40 tabular font-mono">{t}</span>
                    <span className={`text-[11px] font-medium ${c}`}>{ev.event_type}</span>
                    <span className="text-[11px] text-muted-foreground/50 font-mono truncate">
                      {ev.payload?.tool_name ? `tool:${ev.payload.tool_name}` : ""}
                      {ev.payload?.error ? <span className="text-red">{String(ev.payload.error).slice(0, 60)}</span> : ""}
                      {ev.tokens_used ? ` · ${ev.tokens_used} tok` : ""}
                    </span>
                    <span className="text-[11px] text-muted-foreground/30 tabular font-mono">
                      {ev.duration_ms != null ? `${ev.duration_ms}ms` : "—"}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* SYSCALLS */}
        {tab === "SYSCALLS" && (
          <div className="divide-y divide-border/30">
            <div className="grid grid-cols-[90px_130px_100px_1fr_1fr_70px] gap-3 px-5 py-2 os-label bg-background/95 sticky top-0 select-none">
              <span>AGENT</span><span>SYSCALL</span><span>STATUS</span><span>INPUT</span><span>OUTPUT</span><span>DUR</span>
            </div>
            {toolCalls.length === 0 ? (
              <div className="flex items-center justify-center py-12 text-[12px] text-muted-foreground/30">no syscalls recorded</div>
            ) : toolCalls.map((tc) => (
              <div key={tc.id} className="grid grid-cols-[90px_130px_100px_1fr_1fr_70px] gap-3 px-5 py-2.5 hover:bg-accent/40 items-start">
                <span className="pid">{tc.agent_instance_id.slice(0, 8)}</span>
                <span className="text-[11px] font-mono text-amber">{tc.tool_name}</span>
                <span className={`text-[11px] ${TC_COLOR[tc.status] ?? "text-muted-foreground"}`}>{tc.status}</span>
                <pre className="text-[10px] text-muted-foreground/50 overflow-hidden truncate">
                  {JSON.stringify(tc.input_args)}
                </pre>
                <pre className="text-[10px] text-muted-foreground/50 overflow-hidden truncate">
                  {tc.output_result ? JSON.stringify(tc.output_result) : <span className="text-muted-foreground/20">—</span>}
                </pre>
                <span className="text-[11px] text-muted-foreground/30 tabular font-mono">{tc.duration_ms != null ? `${tc.duration_ms}ms` : "—"}</span>
              </div>
            ))}
          </div>
        )}

        {/* OUTPUT */}
        {tab === "OUTPUT" && (
          <div className="p-5">
            <JobOutputViewer outputPayload={job.output_payload} tasks={tasks} liveProgress={liveProgress} />
          </div>
        )}
      </div>
    </div>
  );
}
