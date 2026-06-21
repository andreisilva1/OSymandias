"use client";

import { useEffect, useRef } from "react";
import { useJobs } from "@/hooks/useJobData";
import { useToast } from "@/components/Toast";

const TERMINAL: Record<string, { kind: "success" | "error" | "info"; label: string }> = {
  COMPLETED:        { kind: "success", label: "completed" },
  FAILED:           { kind: "error",   label: "failed" },
  CANCELLED:        { kind: "info",    label: "cancelled" },
  BUDGET_EXCEEDED:  { kind: "error",   label: "budget exceeded" },
};

/** Polls the jobs list and fires a toast whenever any job reaches a terminal
 *  state. Renders nothing. Seeds on first load so pre-existing terminal jobs
 *  don't toast on page open. */
export function LifecycleToaster() {
  const { data: jobs = [] } = useJobs();
  const toast = useToast();
  const prev = useRef<Map<string, string>>(new Map());
  const seeded = useRef(false);

  useEffect(() => {
    const map = prev.current;
    if (!seeded.current) {
      jobs.forEach((j) => map.set(j.id, j.status));
      seeded.current = true;
      return;
    }
    for (const j of jobs) {
      const old = map.get(j.id);
      if (old && old !== j.status && TERMINAL[j.status]) {
        const { kind, label } = TERMINAL[j.status];
        toast({ kind, title: j.title, detail: `job ${label}` });
      }
      map.set(j.id, j.status);
    }
  }, [jobs, toast]);

  return null;
}
