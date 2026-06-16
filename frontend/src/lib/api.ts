import type { Job, Task, AgentDefinition, AgentInstance, ToolDefinition, ToolCall, Message, Event, MetricsSummary, MemoryEntry } from "@/types";

type EventsParams = { limit?: number; job_id?: string; event_type?: string };

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------

export const api = {
  jobs: {
    list: (params?: { status?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams(params as Record<string, string>).toString();
      return request<Job[]>(`/api/v1/jobs${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<Job>(`/api/v1/jobs/${id}`),
    create: (body: { title: string; description?: string; priority?: string; input_payload: Record<string, unknown> }) =>
      request<Job>(`/api/v1/jobs`, { method: "POST", body: JSON.stringify(body) }),
    cancel: (id: string) => request<Job>(`/api/v1/jobs/${id}/cancel`, { method: "PATCH" }),
    tasks: (id: string) => request<Task[]>(`/api/v1/jobs/${id}/tasks`),
    messages: (id: string) => request<Message[]>(`/api/v1/jobs/${id}/messages`),
    toolCalls: (id: string) => request<ToolCall[]>(`/api/v1/jobs/${id}/tool-calls`),
    agentInstances: (id: string) => request<AgentInstance[]>(`/api/v1/jobs/${id}/agents`),
    output: (id: string) => request<Record<string, unknown>>(`/api/v1/jobs/${id}/output`),
    // NOTE: /jobs/{id}/events is SSE — use useJobStream (EventSource) instead of this client
  },

  agents: {
    list: () => request<AgentDefinition[]>(`/api/v1/agents`),
    get: (name: string) => request<AgentDefinition>(`/api/v1/agents/${name}`),
    create: (body: Partial<AgentDefinition>) =>
      request<AgentDefinition>(`/api/v1/agents`, { method: "POST", body: JSON.stringify(body) }),
    update: (name: string, body: Partial<AgentDefinition>) =>
      request<AgentDefinition>(`/api/v1/agents/${name}`, { method: "PUT", body: JSON.stringify(body) }),
    deactivate: (name: string) => request<void>(`/api/v1/agents/${name}`, { method: "DELETE" }),
  },

  tools: {
    list: () => request<ToolDefinition[]>(`/api/v1/tools`),
    get: (name: string) => request<ToolDefinition>(`/api/v1/tools/${name}`),
    create: (body: Partial<ToolDefinition>) =>
      request<ToolDefinition>(`/api/v1/tools`, { method: "POST", body: JSON.stringify(body) }),
    update: (name: string, body: Partial<ToolDefinition>) =>
      request<ToolDefinition>(`/api/v1/tools/${name}`, { method: "PUT", body: JSON.stringify(body) }),
    deactivate: (name: string) => request<void>(`/api/v1/tools/${name}`, { method: "DELETE" }),
  },

  events: {
    list: (params?: EventsParams) => {
      const p = Object.fromEntries(
        Object.entries(params ?? {}).filter(([, v]) => v !== undefined)
      ) as Record<string, string>;
      const qs = new URLSearchParams(p).toString();
      return request<Event[]>(`/api/v1/events${qs ? `?${qs}` : ""}`);
    },
  },

  metrics: {
    summary: () => request<MetricsSummary>(`/api/v1/metrics/summary`),
  },

  providers: {
    models: (provider: string) =>
      request<string[]>(`/api/v1/providers/${provider}/models`),
  },

  memory: {
    list: (params?: { scope?: string; limit?: number }) => {
      const p = Object.fromEntries(
        Object.entries(params ?? {}).filter(([, v]) => v !== undefined)
      ) as Record<string, string>;
      const qs = new URLSearchParams(p).toString();
      return request<MemoryEntry[]>(`/api/v1/memory${qs ? `?${qs}` : ""}`);
    },
  },
};
