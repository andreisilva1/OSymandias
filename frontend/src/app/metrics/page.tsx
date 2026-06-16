"use client";

import { useMetrics } from "@/hooks/useJobData";
import { formatCost, formatTokens } from "@/lib/utils";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from "recharts";
import { Loader2 } from "lucide-react";

const DAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
const PLACEHOLDER = DAYS.map((name) => ({ name, completed: 0, failed: 0 }));

function Stat({ label, value, sub, color = "text-bright" }: {
  label: string; value: string | number; sub?: string; color?: string;
}) {
  return (
    <div className="border border-border bg-card px-4 py-3">
      <div className="text-[9px] tracking-[0.12em] text-muted-foreground/50 uppercase mb-2">{label}</div>
      <div className={`text-[22px] font-semibold tabular leading-none ${color}`}>{value}</div>
      {sub && <div className="text-[10px] text-muted-foreground/40 mt-1">{sub}</div>}
    </div>
  );
}

export default function MetricsPage() {
  const { data: m, isLoading } = useMetrics();

  if (isLoading || !m) {
    return (
      <div className="flex items-center justify-center h-full gap-2 text-muted-foreground">
        <Loader2 className="w-3 h-3 animate-spin" /> loading metrics...
      </div>
    );
  }

  const successRate = (m.success_rate_7d * 100).toFixed(1);
  const rateColor = m.success_rate_7d >= 0.9 ? "text-green" : m.success_rate_7d >= 0.7 ? "text-amber" : "text-red";

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="px-5 py-3 border-b border-border shrink-0">
        <div className="text-[9px] tracking-[0.15em] text-muted-foreground/40 uppercase mb-0.5">OBSERVABILITY / METRICS</div>
        <h1 className="text-sm font-semibold text-bright">System Metrics</h1>
      </div>

      <div className="p-5 space-y-5">
        {/* KPI grid */}
        <div>
          <div className="text-[9px] tracking-[0.15em] text-muted-foreground/40 uppercase mb-2">KEY INDICATORS</div>
          <div className="grid grid-cols-3 gap-3">
            <Stat label="COMPLETED / 24H"   value={m.jobs_completed_last_24h} color="text-green" sub="processes" />
            <Stat label="FAILED / 24H"       value={m.jobs_failed_last_24h}    color="text-red"   sub="processes" />
            <Stat label="SUCCESS RATE / 7D"  value={`${successRate}%`}         color={rateColor}  sub="7-day average" />
            <Stat label="TOKENS / TODAY"      value={formatTokens(m.total_tokens_today)}   color="text-cyan"  sub="processed" />
            <Stat label="COST / TODAY"        value={formatCost(m.total_cost_today)}        color="text-amber" sub="estimated" />
            <Stat label="ACTIVE PROCESSES"   value={m.active_jobs_count}       color="text-bright" sub="running now" />
          </div>
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-2 gap-4">
          {/* Bar chart */}
          <div className="border border-border bg-card p-4">
            <div className="text-[9px] tracking-[0.15em] text-muted-foreground/40 uppercase mb-4">THROUGHPUT (LAST 7 DAYS)</div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={PLACEHOLDER} barGap={3} barSize={12}>
                <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#4a6480", fontFamily: "JetBrains Mono,monospace" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: "#4a6480", fontFamily: "JetBrains Mono,monospace" }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: "#0a1220", border: "1px solid #162230", borderRadius: 2, fontSize: 10, fontFamily: "JetBrains Mono,monospace" }}
                  cursor={{ fill: "rgba(255,255,255,0.02)" }}
                />
                <Bar dataKey="completed" fill="#8FB5A0" radius={0} />
                <Bar dataKey="failed"    fill="#ef4444" radius={0} />
              </BarChart>
            </ResponsiveContainer>
            <div className="flex gap-4 mt-2">
              <span className="flex items-center gap-1.5 text-[9px] text-muted-foreground">
                <span className="w-2 h-2 bg-green-400 inline-block" style={{ background: "#8FB5A0" }} /> completed
              </span>
              <span className="flex items-center gap-1.5 text-[9px] text-muted-foreground">
                <span className="w-2 h-2 inline-block" style={{ background: "#ef4444" }} /> failed
              </span>
            </div>
          </div>

          {/* Success rate gauge */}
          <div className="border border-border bg-card p-4">
            <div className="text-[9px] tracking-[0.15em] text-muted-foreground/40 uppercase mb-4">SUCCESS RATE INDICATOR</div>
            <div className="flex flex-col items-center justify-center h-40 gap-4">
              <div className={`text-[48px] font-semibold tabular leading-none ${rateColor}`}>{successRate}<span className="text-[24px]">%</span></div>
              <div className="w-full">
                <div className="gauge" style={{ height: 8 }}>
                  <div
                    className={`gauge-fill ${m.success_rate_7d >= 0.9 ? "gauge-green" : m.success_rate_7d >= 0.7 ? "gauge-amber" : "gauge-red"}`}
                    style={{ width: `${m.success_rate_7d * 100}%` }}
                  />
                </div>
                <div className="flex justify-between text-[9px] text-muted-foreground/40 mt-1">
                  <span>0%</span><span>50%</span><span>100%</span>
                </div>
              </div>
              <div className="text-[10px] text-muted-foreground">7-day rolling average</div>
            </div>
          </div>
        </div>

        {/* Computed at */}
        {m.computed_at && (
          <div className="text-[10px] text-muted-foreground/30 text-right">
            computed at {new Date(m.computed_at).toLocaleTimeString()}
          </div>
        )}
      </div>
    </div>
  );
}
