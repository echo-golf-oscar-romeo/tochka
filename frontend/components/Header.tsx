"use client";

import Link from "next/link";

interface Props {
  status?: string;
  detail?: string;
  busy?: boolean;
}

export default function Header({ status, detail, busy }: Props) {
  return (
    <header className="relative h-14 shrink-0 flex items-center justify-between border-b border-border bg-canvas/95 backdrop-blur px-5 z-20">
      {/* Hairline accent gradient on top edge */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(70,87,250,0.5) 30%, rgba(70,87,250,0.5) 70%, transparent 100%)",
        }}
      />
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="inline-block h-3 w-3 rounded-sm accent-gradient shadow-pop"
        />
        <div className="flex items-baseline gap-3">
          <span className="display text-lg leading-none">Tochka</span>
          <span className="text-xs text-muted hidden sm:inline">
            Spatial intelligence for HK
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-xs">
          {busy && (
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-500 animate-pulse" />
          )}
          <span className="text-ink font-medium">{status ?? "Idle"}</span>
          {detail && (
            <span className="text-muted truncate max-w-[36ch]">· {detail}</span>
          )}
        </div>
        <Link
          href="/about"
          className="text-xs text-muted hover:text-ink transition rounded-full border border-border w-6 h-6 inline-flex items-center justify-center"
          aria-label="About Tochka"
          title="About"
        >
          ?
        </Link>
      </div>
    </header>
  );
}
