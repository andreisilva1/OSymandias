"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";

type Kind = "success" | "error" | "info";
interface Toast { id: number; kind: Kind; title: string; detail?: string }

const ToastCtx = createContext<(t: Omit<Toast, "id">) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

const STYLE: Record<Kind, { color: string; Icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }> }> = {
  success: { color: "#60A890", Icon: CheckCircle2 },
  error:   { color: "#C06070", Icon: XCircle },
  info:    { color: "#5090A8", Icon: Info },
};

function ToastCard({ t, onClose }: { t: Toast; onClose: () => void }) {
  const { color, Icon } = STYLE[t.kind];
  return (
    <div
      className="flex items-start gap-2.5 w-[320px] px-3.5 py-3 border bg-card rounded-[var(--radius)] shadow-2xl"
      style={{ borderColor: `${color}55`, animation: "toast-in .18s ease-out" }}
    >
      <Icon className="w-4 h-4 shrink-0 mt-px" style={{ color }} />
      <div className="min-w-0 flex-1">
        <div className="text-[12.5px] font-medium text-foreground truncate">{t.title}</div>
        {t.detail && <div className="text-[11px] text-muted-foreground/70 mt-0.5">{t.detail}</div>}
      </div>
      <button onClick={onClose} className="shrink-0 text-muted-foreground/40 hover:text-foreground transition-colors">
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setToasts((p) => [...p, { ...t, id }]);
    setTimeout(() => setToasts((p) => p.filter((x) => x.id !== id)), 6000);
  }, []);

  const remove = (id: number) => setToasts((p) => p.filter((x) => x.id !== id));

  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2">
        {toasts.map((t) => <ToastCard key={t.id} t={t} onClose={() => remove(t.id)} />)}
      </div>
    </ToastCtx.Provider>
  );
}
