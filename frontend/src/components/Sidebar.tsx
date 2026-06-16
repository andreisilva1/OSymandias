"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Cpu, Bot, Terminal, HardDrive, Rss, BarChart2 } from "lucide-react";
import { useJobs } from "@/hooks/useJobData";

type NavItem = {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  liveKey?: string;
};

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "RUNTIME",
    items: [{ label: "Dashboard", href: "/", icon: Activity }],
  },
  {
    section: "KERNEL",
    items: [{ label: "Processes", href: "/jobs", icon: Cpu, liveKey: "running" }],
  },
  {
    section: "SERVICES",
    items: [
      { label: "Agent Registry", href: "/agents", icon: Bot },
      { label: "Syscall Registry", href: "/tools", icon: Terminal },
    ],
  },
  {
    section: "MEMORY",
    items: [{ label: "Memory Layer", href: "/memory", icon: HardDrive }],
  },
  {
    section: "OBSERVABILITY",
    items: [
      { label: "Event Stream", href: "/events", icon: Rss },
      { label: "Metrics", href: "/metrics", icon: BarChart2 },
    ],
  },
];

const INFRA = ["postgres", "redis", "rabbitmq", "qdrant"];

const T = {
  bg:     "#0C0B0A",
  border: "#2E2516",
  gold:   "#C9A84C",
  sage:   "#8FB5A0",
  sand:   "#DDD0B5",
  muted:  "#7A7060",
  dimmed: "#4A4235",
};

export function Sidebar() {
  const pathname = usePathname();
  const { data: jobs = [] } = useJobs();
  const activeCount = jobs.filter(
    (j) => j.status === "RUNNING" || j.status === "PLANNING"
  ).length;

  return (
    <aside
      className="w-48 h-full flex flex-col shrink-0"
      style={{ background: T.bg, borderRight: `1px solid ${T.border}` }}
    >
      {/* Logo */}
      <div className="px-4 pt-4 pb-3" style={{ borderBottom: `1px solid ${T.border}` }}>
        <div className="flex items-center gap-2.5">
          <a href="https://github.com/andreisilva1/OSymandias" target="_blank" rel="noopener noreferrer">
            <img src="/OSymandias.svg" alt="OSymandias" className="w-8 h-8 shrink-0" />
          </a>
          <div>
            <div
              className="text-[10px] font-semibold tracking-[0.18em] uppercase"
              style={{ color: T.gold }}
            >
              OSymandias
            </div>
            <div className="text-[9px] tracking-widest" style={{ color: T.dimmed }}>
              v0.1.0 · runtime
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 space-y-4">
        {NAV.map(({ section, items }) => (
          <div key={section}>
            <div
              className="px-4 mb-1.5 text-[9px] font-semibold tracking-[0.14em] uppercase select-none"
              style={{ color: T.dimmed }}
            >
              {section}
            </div>
            {items.map(({ label, href, icon: Icon, liveKey }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              const count = liveKey === "running" ? activeCount : 0;

              return (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center gap-2.5 px-3 mx-1.5 py-[6px] text-[12px] transition-colors"
                  style={{
                    borderRadius: 3,
                    borderLeft: `2px solid ${active ? T.gold : "transparent"}`,
                    background: active ? "rgba(201,168,76,0.08)" : "transparent",
                    color: active ? T.sand : T.muted,
                  }}
                >
                  <Icon
                    className="w-[13px] h-[13px] shrink-0"
                    style={{ color: active ? T.gold : T.dimmed }}
                  />
                  <span className="flex-1 truncate">{label}</span>
                  {count > 0 && (
                    <span
                      className="text-[10px] px-1.5 py-px rounded tabular font-medium"
                      style={{ background: "rgba(143,181,160,0.14)", color: T.sage }}
                    >
                      {count}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Infra status */}
      <div className="px-4 py-3" style={{ borderTop: `1px solid ${T.border}` }}>
        <div
          className="text-[9px] font-semibold tracking-[0.14em] uppercase mb-2 select-none"
          style={{ color: T.dimmed }}
        >
          INFRA
        </div>
        <div className="space-y-1.5">
          {INFRA.map((svc) => (
            <div key={svc} className="flex items-center gap-2">
              <span
                style={{
                  width: 5, height: 5, borderRadius: "50%",
                  background: T.sage,
                  boxShadow: `0 0 5px ${T.sage}88`,
                  flexShrink: 0,
                }}
              />
              <span className="text-[11px]" style={{ color: T.muted }}>{svc}</span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
