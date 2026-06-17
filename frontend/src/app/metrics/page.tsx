"use client";

import { useMetrics, useMetricsDaily } from "@/hooks/useJobData";
import { formatCost, formatTokens, formatDuration } from "@/lib/utils";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Loader2 } from "lucide-react";

function StatCard({ label, value, sub, color = "#D8E0E8" }: {
  label: string; value: string | number; sub?: string; color?: string;
}) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color }}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export default function MetricsPage() {
  const { data: m, isLoading } = useMetrics();
  const { data: daily = [], isLoading: dailyLoading } = useMetricsDaily();

  if (isLoading || !m) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", gap: 8, color: "#607080", fontSize: 13 }}>
        <Loader2 style={{ width: 14, height: 14 }} className="animate-spin" /> loading metrics...
      </div>
    );
  }

  const successRate = (m.success_rate_7d * 100).toFixed(1);
  const rateColor = m.success_rate_7d >= 0.9 ? "#60A890" : m.success_rate_7d >= 0.7 ? "#C8A040" : "#C06070";
  const avgDurSec = m.avg_job_duration_ms > 0 ? formatDuration(m.avg_job_duration_ms) : "—";

  return (
    <div className="flex flex-col h-full overflow-auto">
      {/* Topbar */}
      <div className="page-topbar">
        <div>
          <div className="page-title">System Metrics</div>
          <div className="page-sub">
            {m.computed_at
              ? `computed at ${new Date(m.computed_at).toLocaleTimeString()}`
              : "live"}
          </div>
        </div>
        {isLoading && <Loader2 style={{ width: 14, height: 14, color: "#607080" }} className="animate-spin" />}
      </div>

      <div className="page-content">

        {/* KPI row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
          <StatCard label="Completed / 24h" value={m.jobs_completed_last_24h} sub="processes" color="#60A890" />
          <StatCard label="Failed / 24h" value={m.jobs_failed_last_24h} sub="processes" color={m.jobs_failed_last_24h > 0 ? "#C06070" : "#D8E0E8"} />
          <StatCard label="Active Now" value={m.active_jobs_count} sub="running + planning" />
          <StatCard label="Avg Duration" value={avgDurSec} sub="7-day completed" color="#5090A8" />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 20 }}>
          <StatCard label="Success Rate / 7d" value={`${successRate}%`} sub="7-day rolling" color={rateColor} />
          <StatCard label="Tokens Today" value={formatTokens(m.total_tokens_today)} sub="processed" color="#5090A8" />
          <StatCard label="Cost Today" value={formatCost(m.total_cost_today)} sub="estimated" color="#C8A040" />
        </div>

        {/* Charts row */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

          {/* Throughput chart */}
          <div className="os-card" style={{ padding: 16 }}>
            <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: "#384858", marginBottom: 14 }}>
              Throughput — last 7 days
            </div>
            {dailyLoading ? (
              <div style={{ height: 160, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Loader2 style={{ width: 14, height: 14, color: "#384858" }} className="animate-spin" />
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={daily} barGap={3} barSize={14}>
                  <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#384858", fontFamily: "inherit" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: "#384858", fontFamily: "inherit" }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ background: "#0C1018", border: "1px solid #1E2830", borderRadius: 6, fontSize: 11, fontFamily: "inherit", color: "#D8E0E8" }}
                    cursor={{ fill: "rgba(255,255,255,0.02)" }}
                  />
                  <Bar dataKey="completed" fill="#60A890" radius={[2, 2, 0, 0]} name="completed" />
                  <Bar dataKey="failed" fill="#C06070" radius={[2, 2, 0, 0]} name="failed" />
                </BarChart>
              </ResponsiveContainer>
            )}
            <div style={{ display: "flex", gap: 16, marginTop: 8 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 9, color: "#607080" }}>
                <span style={{ width: 8, height: 8, background: "#60A890", borderRadius: 1, display: "inline-block" }} /> completed
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 9, color: "#607080" }}>
                <span style={{ width: 8, height: 8, background: "#C06070", borderRadius: 1, display: "inline-block" }} /> failed
              </span>
            </div>
          </div>

          {/* Success rate gauge */}
          <div className="os-card" style={{ padding: 16, display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: "#384858", marginBottom: 14 }}>
              Success Rate Indicator
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16 }}>
              <div style={{ fontSize: 48, fontWeight: 700, color: rateColor, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>
                {successRate}<span style={{ fontSize: 24, fontWeight: 400 }}>%</span>
              </div>
              <div style={{ width: "100%" }}>
                <div style={{ height: 8, background: "#1E2830", borderRadius: 4, overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: 4,
                    width: `${m.success_rate_7d * 100}%`,
                    background: rateColor,
                    transition: "width 0.6s ease",
                  }} />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "#283040", marginTop: 4 }}>
                  <span>0%</span><span>50%</span><span>100%</span>
                </div>
              </div>
              <div style={{ fontSize: 10, color: "#607080" }}>7-day rolling average</div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
