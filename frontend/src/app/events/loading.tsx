export default function Loading() {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border shrink-0">
        <div className="space-y-1.5">
          <div className="h-2.5 w-36 bg-border/60 rounded animate-pulse" />
          <div className="h-4 w-24 bg-border/40 rounded animate-pulse" />
        </div>
      </div>
      <div className="flex-1 p-4 space-y-1">
        {Array.from({ length: 14 }).map((_, i) => (
          <div key={i} className="h-8 bg-card border border-border/40 rounded animate-pulse" style={{ opacity: 1 - i * 0.05 }} />
        ))}
      </div>
    </div>
  );
}
