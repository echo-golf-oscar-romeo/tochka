"use client";

import { type ReactNode } from "react";

export type Workflow = "diagnose" | "expand" | "rationalise";

interface Props {
  networkId: string | null;
  activeWorkflow: Workflow | null;
  busy: boolean;
  onUpload: () => void;
  onRunWorkflow: (w: Workflow) => void;
  onBeautify: () => void;
  beautifying: boolean;
  onOpenStorymap: () => void;
  storymapReady: boolean;
}

interface ToolButton {
  id: Workflow;
  label: string;
  sub: string;
}

const WORKFLOWS: ToolButton[] = [
  { id: "diagnose",    label: "Diagnose",    sub: "How is the network performing?" },
  { id: "expand",      label: "Expand",      sub: "Where to open next?" },
  { id: "rationalise", label: "Rationalise", sub: "What to close / merge?" },
];

export default function Toolkit(props: Props) {
  const {
    networkId, activeWorkflow, busy, beautifying,
    onUpload, onRunWorkflow, onBeautify, onOpenStorymap, storymapReady,
  } = props;
  const disabled = !networkId || busy;

  return (
    <aside className="w-72 shrink-0 bg-white/95 backdrop-blur border-r border-muted/30 flex flex-col h-full overflow-y-auto">
      <div className="px-5 pt-5 pb-3 border-b border-muted/20">
        <div className="font-serif text-lg">Tochka</div>
        <div className="text-[11px] uppercase tracking-wider text-muted">Location intelligence</div>
      </div>

      <Section title="Data">
        <button
          type="button"
          onClick={onUpload}
          disabled={busy}
          className="w-full rounded border border-muted/30 hover:border-accent px-3 py-2 text-left text-sm disabled:opacity-50"
        >
          <div className="font-medium text-ink">{networkId ? "Replace network…" : "Upload network CSV…"}</div>
          <div className="text-xs text-muted">
            {networkId ? `Loaded · ${networkId.slice(0, 8)}…` : "Drag your locations to start"}
          </div>
        </button>
      </Section>

      <Section title="Analysis toolkit">
        {WORKFLOWS.map((w) => (
          <button
            key={w.id}
            type="button"
            disabled={disabled}
            onClick={() => onRunWorkflow(w.id)}
            className={`w-full rounded border px-3 py-2 text-left transition disabled:opacity-40 disabled:cursor-not-allowed ${
              activeWorkflow === w.id
                ? "border-accent bg-accent/10"
                : "border-muted/30 hover:border-muted/60 bg-white"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-serif text-base">{w.label}</span>
              {activeWorkflow === w.id && (
                <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
              )}
            </div>
            <div className="text-[11px] text-muted mt-0.5">{w.sub}</div>
          </button>
        ))}
      </Section>

      <Section title="Refinement">
        <button
          type="button"
          onClick={onBeautify}
          disabled={disabled || beautifying}
          className="w-full rounded border border-muted/30 hover:border-warm px-3 py-2 text-left disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium text-ink">
              {beautifying ? "Beautifying…" : "Beautify map"}
            </span>
            {beautifying && (
              <span className="inline-block h-2 w-2 rounded-full bg-warm animate-pulse" />
            )}
          </div>
          <div className="text-[11px] text-muted mt-0.5">Vision agent restyles the canvas. 2–3 passes.</div>
        </button>
      </Section>

      <Section title="Output">
        <button
          type="button"
          onClick={onOpenStorymap}
          disabled={!storymapReady}
          className="w-full rounded border border-muted/30 hover:border-accent px-3 py-2 text-left disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <div className="font-medium text-ink">Open storymap</div>
          <div className="text-[11px] text-muted mt-0.5">
            {storymapReady ? "Scroll-driven five-section narrative" : "Run an analysis first"}
          </div>
        </button>
      </Section>

      <div className="flex-1" />
      <div className="px-5 py-3 text-[10px] text-muted border-t border-muted/20">
        Powered by Qwen / DeepSeek · grounded in CSDI + OSM · MapLibre
      </div>
    </aside>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="px-5 py-4 border-b border-muted/15">
      <div className="text-[10px] uppercase tracking-wider text-muted mb-2">{title}</div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}
