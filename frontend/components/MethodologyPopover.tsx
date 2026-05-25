"use client";

import { useEffect, useState } from "react";

export interface Plan {
  text: string;                // LLM-narrated methodology
  archetypes: string[];        // ["diagnose"] etc.
  tool_sequence: string[];     // ordered list of tool names the run will execute
}

interface Props {
  plan: Plan | null;
  currentTool: string | null;        // the tool currently running (from last tool_call)
  completedTools: Set<string>;       // tools that have emitted tool_result
  done: boolean;                     // run finished (done | storymap_ready)
  onDismiss: () => void;
}

/**
 * Floating "methodology" pop-over. Appears when a workflow run emits its
 * plan_narrative, ticks tools off as tool_result events stream in, and
 * stays visible after `done` so the user can review what happened. The
 * user can collapse it to a chip at any time.
 */
export default function MethodologyPopover({
  plan, currentTool, completedTools, done, onDismiss,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);

  // Re-expand whenever a new plan arrives.
  useEffect(() => {
    if (plan) setCollapsed(false);
  }, [plan]);

  if (!plan) return null;

  const completedCount = plan.tool_sequence.filter((t) => completedTools.has(t)).length;
  const total = plan.tool_sequence.length;

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        className="absolute left-1/2 top-3 -translate-x-1/2 z-20 rounded-full liquid-glass px-3 py-1.5 text-xs text-ink hover:border-accent-400 transition"
      >
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-500 align-middle mr-2" />
        Methodology · {completedCount}/{total}
      </button>
    );
  }

  return (
    <div className="absolute left-1/2 top-3 -translate-x-1/2 z-20 w-[34rem] max-w-[92%] rounded-lg liquid-glass-strong overflow-hidden">
      <div className="flex items-start justify-between px-4 pt-3 pb-2 border-b border-border">
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-wider text-muted">
            Methodology · {plan.archetypes.join(" + ")}
          </div>
          <div className="text-xs text-ink mt-0.5 truncate">
            {done
              ? "Run complete — methodology archived below"
              : currentTool
                ? `Running: ${prettyTool(currentTool)}`
                : "Planning…"}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[11px] text-muted tabular-nums">
            {completedCount}/{total}
          </span>
          <button
            type="button"
            onClick={() => setCollapsed(true)}
            aria-label="Collapse"
            className="text-muted hover:text-ink w-6 h-6 inline-flex items-center justify-center rounded-full hover:bg-rule transition"
            title="Collapse"
          >
            –
          </button>
          {done && (
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Dismiss"
              className="text-muted hover:text-ink w-6 h-6 inline-flex items-center justify-center rounded-full hover:bg-rule transition"
              title="Dismiss"
            >
              ×
            </button>
          )}
        </div>
      </div>

      <div className="px-4 py-3 text-[13px] text-ink leading-relaxed max-h-72 overflow-y-auto whitespace-pre-wrap">
        {plan.text}
      </div>

      <ul className="border-t border-border px-4 py-2 space-y-1 max-h-44 overflow-y-auto">
        {plan.tool_sequence.map((tool) => {
          const isDone = completedTools.has(tool);
          const isCurrent = currentTool === tool && !isDone;
          return (
            <li key={tool} className="flex items-center gap-2 text-xs">
              <span
                aria-hidden
                className={`inline-flex items-center justify-center h-4 w-4 rounded-full border text-[10px] font-medium shrink-0 ${
                  isDone
                    ? "bg-accent-500 border-accent-500 text-canvas"
                    : isCurrent
                      ? "border-accent-500 text-accent-600 animate-pulse"
                      : "border-border text-subtle"
                }`}
              >
                {isDone ? "✓" : isCurrent ? "·" : ""}
              </span>
              <span className={isDone ? "text-muted line-through" : isCurrent ? "text-ink font-medium" : "text-ink"}>
                {prettyTool(tool)}
              </span>
            </li>
          );
        })}
      </ul>

      {!done && (
        <div className="h-0.5 bg-rule">
          <div
            className="h-full bg-accent-500 transition-all"
            style={{ width: total > 0 ? `${(completedCount / total) * 100}%` : "0%" }}
          />
        </div>
      )}
    </div>
  );
}

function prettyTool(t: string): string {
  return t
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
