"use client";

import { useCallback } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
} from "reactflow";
import "reactflow/dist/style.css";
import type { AgentInstance, Message } from "@/types";
import { StatusBadge } from "@/components/jobs/JobStatusBadge";

interface Props {
  instances: AgentInstance[];
  messages: Message[];
}

const STATUS_COLOR: Record<string, string> = {
  RUNNING: "#3b82f6",
  TERMINATED: "#10b981",
  CRASHED: "#ef4444",
  BLOCKED: "#f59e0b",
  CREATED: "#71717a",
  READY: "#f59e0b",
  SUSPENDED: "#f59e0b",
};

export function AgentGraph({ instances, messages }: Props) {
  const initialNodes = instances.map((inst, i) => ({
    id: inst.id,
    position: { x: (i % 3) * 220 + 40, y: Math.floor(i / 3) * 140 + 40 },
    data: {
      label: (
        <div className="text-left space-y-1">
          <p className="text-xs font-semibold truncate">{inst.agent_definition_name}</p>
          <p className="text-xs text-muted-foreground">iter: {inst.iteration_count}</p>
          <StatusBadge status={inst.status} />
        </div>
      ),
    },
    style: {
      background: "#0f172a",
      border: `1px solid ${STATUS_COLOR[inst.status] ?? "#334155"}`,
      borderRadius: 8,
      padding: 10,
      color: "#f1f5f9",
      fontSize: 11,
      width: 180,
    },
  }));

  const initialEdges = messages.map((msg) => ({
    id: msg.id,
    source: msg.sender_agent_instance_id,
    target: msg.receiver_agent_instance_id ?? msg.sender_agent_instance_id,
    label: msg.subject,
    animated: !msg.is_read,
    style: { stroke: "#3b82f6", strokeWidth: 1.5 },
    labelStyle: { fill: "#94a3b8", fontSize: 9 },
    labelBgStyle: { fill: "#0f172a" },
  }));

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const onConnect = useCallback((c: Connection) => setEdges((eds) => addEdge(c, eds)), [setEdges]);

  return (
    <div className="h-[480px] rounded-lg border border-border overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        fitView
        attributionPosition="bottom-right"
      >
        <Background color="#1e293b" gap={24} />
        <Controls />
        <MiniMap nodeColor={(n) => (n.style?.borderColor as string) ?? "#334155"} />
      </ReactFlow>
    </div>
  );
}
