"use client";

interface Props {
  status?: string;
  detail?: string;
  busy?: boolean;
}

export default function Header({ status, detail, busy }: Props) {
  return (
    <header className="h-12 shrink-0 flex items-center justify-between border-b border-border bg-canvas px-4 z-20">
      <div className="flex items-center gap-3">
        <div className="h-2.5 w-2.5 rounded-sm bg-accent-500" aria-hidden />
        <span className="font-semibold text-ink tracking-tightish">Tochka</span>
        <span className="text-xs text-muted">Location intelligence</span>
      </div>
      <div className="flex items-center gap-2 text-xs">
        {busy && (
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-500 animate-pulse" />
        )}
        <span className="text-ink">{status ?? "Idle"}</span>
        {detail && <span className="text-muted">· {detail}</span>}
      </div>
    </header>
  );
}
