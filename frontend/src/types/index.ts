// ---------------------------------------------------------------------------
// Job
// ---------------------------------------------------------------------------

export type JobStatus = "PENDING" | "PLANNING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED" | "BUDGET_EXCEEDED";
export type JobPriority = "HIGH" | "NORMAL" | "LOW";

export interface Job {
  id: string;
  title: string;
  description?: string;
  status: JobStatus;
  priority: JobPriority;
  input_payload: Record<string, unknown>;
  output_payload?: Record<string, unknown>;
  retry_policy: { max_attempts: number; backoff: string; backoff_seconds: number };
  total_tokens: number;
  estimated_cost: number;
  max_tokens?: number | null;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

// ---------------------------------------------------------------------------
// Task
// ---------------------------------------------------------------------------

export type TaskStatus =
  | "PENDING"
  | "WAITING"
  | "READY"
  | "ASSIGNED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "RETRYING"
  | "CANCELLED"
  | "HUMAN_REVIEW";

export interface Task {
  id: string;
  job_id: string;
  parent_task_id?: string;
  title: string;
  description?: string;
  status: TaskStatus;
  agent_type?: string;
  agent_instance_id?: string;
  input_context: Record<string, unknown>;
  output_result?: Record<string, unknown>;
  attempt_count: number;
  max_attempts: number;
  requires_approval: boolean;
  evaluation_score?: number;
  evaluation_feedback?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  depends_on?: string[];
}

// ---------------------------------------------------------------------------
// Agent
// ---------------------------------------------------------------------------

export interface AgentDefinition {
  name: string;
  version: string;
  description?: string;
  role: string;
  system_prompt_template: string;
  allowed_tools: string[];
  llm_provider: string;
  llm_model: string;
  max_iterations: number;
  timeout_seconds: number;
  output_schema?: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  agent_kind?: "builtin" | "external";
  callable_ref?: string;
  framework?: string;
}

export type AgentInstanceStatus =
  | "CREATED"
  | "READY"
  | "RUNNING"
  | "BLOCKED"
  | "SUSPENDED"
  | "TERMINATED"
  | "CRASHED";

export interface AgentInstance {
  id: string;
  job_id: string;
  task_id?: string;
  agent_definition_name: string;
  status: AgentInstanceStatus;
  iteration_count: number;
  tokens_used: number;
  estimated_cost: number;
  tool_calls_count: number;
  last_heartbeat_at?: string;
  created_at: string;
  terminated_at?: string;
}

// ---------------------------------------------------------------------------
// Message
// ---------------------------------------------------------------------------

export type MessageType = "TASK_RESULT" | "DATA_SHARE" | "REQUEST" | "BROADCAST";

export interface Message {
  id: string;
  job_id: string;
  sender_agent_instance_id: string;
  receiver_agent_instance_id?: string;
  receiver_agent_type?: string;
  message_type: MessageType;
  subject: string;
  content: Record<string, unknown>;
  is_read: boolean;
  sent_at: string;
  read_at?: string;
}

// ---------------------------------------------------------------------------
// Tool Call
// ---------------------------------------------------------------------------

export type ToolCallStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCESS"
  | "FAILED"
  | "TIMEOUT"
  | "PERMISSION_DENIED";

export interface ToolCall {
  id: string;
  job_id: string;
  task_id: string;
  agent_instance_id: string;
  tool_name: string;
  input_args: Record<string, unknown>;
  output_result?: Record<string, unknown>;
  status: ToolCallStatus;
  attempt_count: number;
  error_message?: string;
  created_at: string;
  completed_at?: string;
  duration_ms?: number;
  estimated_cost: number;
}

// ---------------------------------------------------------------------------
// Event
// ---------------------------------------------------------------------------

export interface Event {
  id: string;
  job_id?: string;
  task_id?: string;
  agent_instance_id?: string;
  event_type: string;
  payload: Record<string, unknown>;
  tokens_used?: number;
  estimated_cost?: number;
  duration_ms?: number;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Tool Definition
// ---------------------------------------------------------------------------

export interface ToolDefinition {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  rate_limit_per_minute?: number;
  requires_external_api: boolean;
  webhook_url?: string;
  is_active: boolean;
  created_at?: string;
}

// ---------------------------------------------------------------------------
// Metrics
// ---------------------------------------------------------------------------

export interface MetricsSummary {
  jobs_completed_last_24h: number;
  jobs_failed_last_24h: number;
  success_rate_7d: number;
  total_tokens_today: number;
  total_cost_today: number;
  active_jobs_count: number;
  avg_job_duration_ms: number;
  computed_at?: string;
}

export interface MemoryEntry {
  id: string;
  scope: "TASK" | "JOB" | "GLOBAL";
  scope_id?: string;
  key: string;
  value: Record<string, unknown>;
  access_count: number;
  created_at: string;
  last_accessed_at?: string;
  expires_at?: string;
}

// ---------------------------------------------------------------------------
// Production controls (1.1)
// ---------------------------------------------------------------------------

export interface CostBreakdown {
  by_agent: { agent: string; tokens: number; cost: number; instances: number }[];
  by_tool: { tool: string; calls: number; cost: number }[];
  total_tokens: number;
  total_cost: number;
}

export interface TaskTrace {
  task: { id: string; title: string; status: string; agent_type?: string; output_result?: Record<string, unknown> };
  events: { event_type: string; payload: Record<string, unknown>; timestamp: string; tokens_used?: number; duration_ms?: number }[];
  tool_calls: { tool_name: string; input_args?: Record<string, unknown>; output_result?: Record<string, unknown>; status: string; duration_ms?: number }[];
  conversation: { role: string; content?: string; tool_calls?: unknown }[];
}

export interface Webhook {
  id: string;
  url: string;
  events?: string[] | null;
  is_active: boolean;
  created_at: string;
}
