export default function RootLoading() {
  return (
    <div className="flex items-center justify-center h-full gap-2 text-muted-foreground text-[12px]">
      <span className="dot dot-running" style={{ width: 6, height: 6 }} />
      <span>loading…</span>
    </div>
  );
}
