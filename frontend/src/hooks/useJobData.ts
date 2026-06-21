"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useJobs(params?: { status?: string }) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () => api.jobs.list(params),
  });
}

export function useJob(id: string | null) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: () => api.jobs.get(id!),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data?.status === "RUNNING" || query.state.data?.status === "PLANNING" ? 3000 : false,
  });
}

export function useJobTasks(jobId: string | null) {
  return useQuery({
    queryKey: ["job-tasks", jobId],
    queryFn: () => api.jobs.tasks(jobId!),
    enabled: !!jobId,
    refetchInterval: 5000,
  });
}

export function useJobToolCalls(jobId: string | null) {
  return useQuery({
    queryKey: ["job-tool-calls", jobId],
    queryFn: () => api.jobs.toolCalls(jobId!),
    enabled: !!jobId,
  });
}

export function useJobMessages(jobId: string | null) {
  return useQuery({
    queryKey: ["job-messages", jobId],
    queryFn: () => api.jobs.messages(jobId!),
    enabled: !!jobId,
  });
}

export function useJobAgentInstances(jobId: string | null) {
  return useQuery({
    queryKey: ["job-agents", jobId],
    queryFn: () => api.jobs.agentInstances(jobId!),
    enabled: !!jobId,
    refetchInterval: 3000,
  });
}

export function useJobCostBreakdown(jobId: string | null) {
  return useQuery({
    queryKey: ["job-cost", jobId],
    queryFn: () => api.jobs.costBreakdown(jobId!),
    enabled: !!jobId,
  });
}

export function useTaskTrace(jobId: string | null, taskId: string | null) {
  return useQuery({
    queryKey: ["task-trace", jobId, taskId],
    queryFn: () => api.jobs.trace(jobId!, taskId!),
    enabled: !!jobId && !!taskId,
  });
}

export function useTasksByStatus(status: string) {
  return useQuery({
    queryKey: ["tasks", status],
    queryFn: () => api.tasks.list({ status }),
    refetchInterval: 5000,
  });
}

export function useWebhooks() {
  return useQuery({
    queryKey: ["webhooks"],
    queryFn: () => api.webhooks.list(),
  });
}

export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: () => api.metrics.summary(),
    refetchInterval: 30_000,
  });
}

export function useMetricsDaily() {
  return useQuery({
    queryKey: ["metrics-daily"],
    queryFn: () => api.metrics.daily(),
    refetchInterval: 60_000,
  });
}

export function useAgents() {
  return useQuery({
    queryKey: ["agents"],
    queryFn: () => api.agents.list(),
  });
}

export function useTools() {
  return useQuery({
    queryKey: ["tools"],
    queryFn: () => api.tools.list(),
  });
}

export function useEvents(params?: { limit?: number; job_id?: string; event_type?: string }) {
  return useQuery({
    queryKey: ["events", params],
    queryFn: () => api.events.list(params),
    refetchInterval: 3000,
  });
}

export function useMemory(params?: { scope?: string; limit?: number }) {
  return useQuery({
    queryKey: ["memory", params],
    queryFn: () => api.memory.list(params),
    refetchInterval: 10_000,
  });
}
