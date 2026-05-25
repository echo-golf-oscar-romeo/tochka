"use client";

import Link from "next/link";
import type { Workflow } from "./WorkspacePanel";

interface Props {
  status?: string;
  detail?: string;
  busy?: boolean;
  // Workflow buttons live in the header now, not the sidebar
  activeWorkflow?: Workflow | null;
  onRunWorkflow?: (w: Workflow) => void;
  workflowsDisabled?: boolean;
}

const WORKFLOWS: { id: Workflow; label: string }[] = [
  { id: "diagnose",    label: "Diagnose" },
  { id: "expand",      label: "Expand" },
  { id: "rationalise", label: "Rationalise" },
];

export default function Header({
  status, detail, busy, activeWorkflow, onRunWorkflow, workflowsDisabled,
}: Props) {
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

      {/* Workflow buttons live in the header now */}
      {onRunWorkflow && (
        <div className="flex items-center gap-1 mx-6">
          {WORKFLOWS.map((w) => (
            <button
              key={w.id}
              type="button"
              onClick={() => onRunWorkflow(w.id)}
              disabled={workflowsDisabled}
              className={`text-xs px-3 py-1.5 rounded-full transition disabled:opacity-40 disabled:cursor-not-allowed ${
                activeWorkflow === w.id
                  ? "bg-accent-500 text-canvas"
                  : "text-ink hover:bg-rule"
              }`}
            >
              {w.label}
              {activeWorkflow === w.id && (
                <span className="ml-1.5 inline-block h-1 w-1 rounded-full bg-white/80 align-middle animate-pulse" />
              )}
            </button>
          ))}
        </div>
      )}

      <div className="flex-1" />

      <div className="flex items-center gap-3">
        <div className="text-xs flex items-center gap-2">
          {busy && (
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-500 animate-pulse" />
          )}
          <span className="text-ink font-medium">{status ?? "Idle"}</span>
          {detail && (
            <span className="text-muted hidden md:inline truncate max-w-[40ch]">· {detail}</span>
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
