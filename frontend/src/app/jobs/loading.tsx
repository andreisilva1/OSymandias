export default function Loading() {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border shrink-0">
        <div className="space-y-1.5">
          <div className="h-2.5 w-20 bg-border/60 rounded animate-pulse" />
          <div className="h-4 w-28 bg-border/40 rounded animate-pulse" />
        </div>
      </div>
      <div className="flex-1 p-5 space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-12 bg-card border border-border rounded-[var(--radius)] animate-pulse" style={{ opacity: 1 - i * 0.12 }} />
        ))}
      </div>
    </div>
  );
}
