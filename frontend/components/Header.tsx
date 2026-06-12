"use client";

import Link from "next/link";

interface Props {
  status?: string;
  detail?: string;
  busy?: boolean;
}

export default function Header({ status, detail, busy }: Props) {
  return (
    <header className="h-12 shrink-0 flex items-center border-b border-border liquid-glass px-4 z-20">
      {/* Brand: a single dot + the wordmark (lowercase) */}
      <div className="flex items-center gap-2.5 shrink-0">
        <span
          aria-hidden
          className="inline-block h-2.5 w-2.5 rounded-full accent-gradient shadow-sm"
        />
        <span className="text-sm font-semibold text-ink tracking-tightish lowercase">tochka</span>
      </div>

      <div className="flex-1" />

      <div className="flex items-center gap-3">
        <div className="text-xs flex items-center gap-2">
          {busy && (
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-500 animate-pulse" />
          )}
          <span className="text-ink font-medium">{status ?? "Idle"}</span>
          {detail && (
            <span className="text-muted hidden md:inline truncate max-w-[48ch]">· {detail}</span>
          )}
        </div>
        <Link
          href="/about"
          className="text-[11px] text-muted hover:text-ink rounded-full border border-border w-6 h-6 inline-flex items-center justify-center transition"
          aria-label="About tochka"
          title="About"
        >
          ?
        </Link>
      </div>
    </header>
  );
}
