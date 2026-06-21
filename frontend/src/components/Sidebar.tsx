"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Cpu, Bot, Terminal, HardDrive, Rss, BarChart2, Webhook, ShieldCheck } from "lucide-react";
import { useJobs, useTasksByStatus } from "@/hooks/useJobData";

type NavItem = {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  liveKey?: string;
};

const NAV: { section: string; items: NavItem[] }[] = [
  { section: "RUNTIME",      items: [{ label: "Dashboard",      href: "/",       icon: Activity }] },
  { section: "KERNEL",       items: [
    { label: "Processes",      href: "/jobs",      icon: Cpu, liveKey: "running" },
    { label: "Approvals",      href: "/approvals", icon: ShieldCheck, liveKey: "approvals" },
  ]},
  { section: "SERVICES",     items: [
    { label: "Agent Registry",  href: "/agents", icon: Bot },
    { label: "Syscall Registry",href: "/tools",  icon: Terminal },
  ]},
  { section: "MEMORY",       items: [{ label: "Memory Layer",   href: "/memory", icon: HardDrive }] },
  { section: "OBSERVABILITY",items: [
    { label: "Event Stream", href: "/events",   icon: Rss },
    { label: "Metrics",      href: "/metrics",  icon: BarChart2 },
    { label: "Webhooks",     href: "/webhooks", icon: Webhook },
  ]},
];

const INFRA = ["postgres", "redis", "rabbitmq", "qdrant"];

export function Sidebar() {
  const pathname = usePathname();
  const { data: jobs = [] } = useJobs();
  const { data: pendingApprovals = [] } = useTasksByStatus("HUMAN_REVIEW");
  const activeCount = jobs.filter(
    (j) => j.status === "RUNNING" || j.status === "PLANNING"
  ).length;
  const approvalsCount = pendingApprovals.length;

  return (
    <aside style={{
      width: 216,
      background: "#0C1018",
      borderRight: "1px solid #1E2830",
      display: "flex", flexDirection: "column",
      flexShrink: 0, height: "100%", position: "relative",
    }}>
      {/* Antique gold top accent */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 2,
        background: "linear-gradient(90deg, #906010, #C8A040, #E8C060, #C8A040, #906010)",
      }} />

      {/* Logo */}
      <div style={{
        padding: "20px 16px 14px", marginTop: 2,
        borderBottom: "1px solid #1E2830",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <img
            src="/OSymandias_nobg.svg"
            alt="OSymandias"
            style={{ width: 32, height: 32, flexShrink: 0 }}
          />
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#D8E0E8", letterSpacing: "-0.2px" }}>
              OSymandias
            </div>
            <div style={{ fontSize: 10, fontWeight: 300, color: "#384858", marginTop: 1 }}>
              v1.1.1 · runtime
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, overflowY: "auto", padding: "12px 0" }}>
        {NAV.map(({ section, items }) => (
          <div key={section} style={{ marginBottom: 16 }}>
            <div style={{
              padding: "0 16px", marginBottom: 4,
              fontSize: 9, fontWeight: 600,
              letterSpacing: "0.12em", textTransform: "uppercase",
              color: "#283040", userSelect: "none",
            }}>
              {section}
            </div>
            {items.map(({ label, href, icon: Icon, liveKey }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              const count = liveKey === "running" ? activeCount : liveKey === "approvals" ? approvalsCount : 0;
              const amber = liveKey === "approvals";
              return (
                <Link key={href} href={href} className={`nav-item${active ? " active" : ""}`}>
                  <Icon className="nav-icon" />
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {label}
                  </span>
                  {count > 0 && (
                    <span style={{
                      fontSize: 10, padding: "1px 6px", borderRadius: 10,
                      background: amber ? "rgba(200,160,64,0.14)" : "rgba(96,168,144,0.12)",
                      color: amber ? "#C8A040" : "#60A890",
                      fontWeight: 500, fontVariantNumeric: "tabular-nums",
                    }}>
                      {count}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Infra */}
      <div style={{ padding: "12px 16px 16px", borderTop: "1px solid #1E2830" }}>
        <div style={{
          fontSize: 9, fontWeight: 600, letterSpacing: "0.12em",
          textTransform: "uppercase", color: "#283040",
          marginBottom: 8, userSelect: "none",
        }}>
          INFRA
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {INFRA.map((svc) => (
            <div key={svc} style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span style={{
                width: 5, height: 5, borderRadius: "50%",
                background: "#60A890", boxShadow: "0 0 4px rgba(96,168,144,0.5)",
                flexShrink: 0,
              }} />
              <span style={{ fontSize: 11, color: "#607080" }}>{svc}</span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
