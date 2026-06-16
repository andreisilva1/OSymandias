"use client";

import { useEffect, useRef, useState } from "react";
import type { Event } from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface UseJobStreamOptions {
  onEvent?: (event: Event) => void;
}

export function useJobStream(jobId: string | null, options: UseJobStreamOptions = {}) {
  const [events, setEvents] = useState<Event[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const { onEvent } = options;

  useEffect(() => {
    if (!jobId) return;

    const url = `${BASE}/api/v1/jobs/${jobId}/events`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (e) => {
      try {
        const event: Event = JSON.parse(e.data);
        setEvents((prev) => [event, ...prev]);
        onEvent?.(event);
      } catch {
        // ignore malformed frames
      }
    };

    es.onerror = () => {
      setConnected(false);
      // browser auto-reconnects SSE; no manual retry needed
    };

    return () => {
      es.close();
      setConnected(false);
    };
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  return { events, connected };
}
