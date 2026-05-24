"use client";

import { type ReactNode } from "react";
import ChatPanel from "./ChatPanel";
import LayersList from "./LayersList";
import type { Layer as StoryLayer } from "@/lib/storymap";

export type Workflow = "diagnose" | "expand" | "rationalise";

interface Props {
  // Data
  networkId: string | null;
  networkSummary: string | null;
  onUpload: () => void;

  // Workflow
  activeWorkflow: Workflow | null;
  busy: boolean;
  onRunWorkflow: (w: Workflow) => void;

  // Layers
  layers: StoryLayer[];
  layerVisibility: Record<string, boolean>;
  onToggleLayer: (id: string, visible: boolean) => void;
  onRemoveLayer: (id: string) => void;

  // Outputs
  storymapReady: boolean;
  onOpenStorymap: () => void;
  beautifying: boolean;
  onBeautify: () => void;
  beautifyNotice?: string | null;

  // Chat
  storymapIdForChat: string | null;
  chatSuggestions: string[];
  layerNames: string[];
  onAddPointsToMap?: (label: string, points: { id: string; lat: number; lng: number; label?: string }[]) => void;
}

const WORKFLOWS: { id: Workflow; label: string; sub: string }[] = [
  { id: "diagnose",    label: "Diagnose",    sub: "How is the network performing?" },
  { id: "expand",      label: "Expand",      sub: "Where to open next?" },
  { id: "rationalise", label: "Rationalise", sub: "What to close or merge?" },
];

export default function WorkspacePanel(props: Props) {
  const {
    networkId, networkSummary, onUpload,
    activeWorkflow, busy, onRunWorkflow,
    layers, layerVisibility, onToggleLayer, onRemoveLayer,
    storymapReady, onOpenStorymap, beautifying, onBeautify, beautifyNotice,
    storymapIdForChat, chatSuggestions, layerNames, onAddPointsToMap,
  } = props;
  const disabled = !networkId || busy;

  return (
    <aside className="w-[26rem] shrink-0 border-l border-border bg-canvas flex flex-col h-full overflow-hidden">
      {/* Data */}
      <Section title="Data">
        <button
          type="button"
          onClick={onUpload}
          className="w-full rounded border border-border hover:border-accent-400 hover:bg-accent-50 px-3 py-2 text-left"
        >
          <div className="text-sm font-medium text-ink">
            {networkId ? "Replace network" : "Upload network CSV"}
          </div>
          <div className="text-xs text-muted mt-0.5">
            {networkSummary ?? "Drag your locations to start"}
          </div>
        </button>
      </Section>

      {/* Workflows */}
      <Section title="Run analysis">
        <div className="grid grid-cols-3 gap-2">
          {WORKFLOWS.map((w) => (
            <button
              key={w.id}
              type="button"
              disabled={disabled}
              onClick={() => onRunWorkflow(w.id)}
              className={`rounded border px-2 py-2 text-left transition disabled:opacity-40 disabled:cursor-not-allowed ${
                activeWorkflow === w.id
                  ? "border-accent-500 bg-accent-50"
                  : "border-border hover:border-accent-300"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-ink">{w.label}</span>
                {activeWorkflow === w.id && (
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-500 animate-pulse" />
                )}
              </div>
              <div className="text-[11px] text-muted mt-0.5 leading-snug">{w.sub}</div>
            </button>
          ))}
        </div>
      </Section>

      {/* Layers */}
      <Section title={`Layers ${layers.length > 0 ? `· ${layers.length}` : ""}`}>
        <LayersList
          layers={layers}
          visibility={layerVisibility}
          onToggle={onToggleLayer}
          onRemove={onRemoveLayer}
        />
      </Section>

      {/* Outputs */}
      <Section title="Refinement & output" tight>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onBeautify}
            disabled={disabled || beautifying}
            className="rounded border border-border hover:border-accent-400 px-3 py-2 text-left text-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <div className="flex items-center justify-between">
              <span className="font-medium">{beautifying ? "Beautifying…" : "Beautify map"}</span>
              {beautifying && (
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-500 animate-pulse" />
              )}
            </div>
            <div className="text-[10px] text-muted mt-0.5">Vision pass · 2–3 iters</div>
          </button>
          <button
            type="button"
            onClick={onOpenStorymap}
            disabled={!storymapReady}
            className="rounded border border-border hover:border-accent-400 px-3 py-2 text-left text-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <div className="font-medium">Open storymap</div>
            <div className="text-[10px] text-muted mt-0.5">
              {storymapReady ? "Five-section narrative" : "Run an analysis first"}
            </div>
          </button>
        </div>
      </Section>

      {beautifyNotice && (
        <div className="px-4 py-2 border-b border-border bg-highlight-50 text-[11px] text-ink">
          <span className="font-medium">Beautify:</span> {beautifyNotice}
        </div>
      )}

      {/* Chat — takes remaining vertical space */}
      <div className="flex-1 min-h-0 flex flex-col border-t border-border">
        <div className="px-4 pt-3 pb-2 flex items-center justify-between">
          <div className="text-[10px] uppercase tracking-wider text-muted">Ask the data</div>
          <div className="text-[10px] text-subtle">
            {networkId ? "Spatial SQL · DuckDB" : "Upload first"}
          </div>
        </div>
        <div className="flex-1 min-h-0">
          {networkId ? (
            <ChatPanel
              storymapId={storymapIdForChat ?? undefined}
              networkId={networkId}
              suggestions={chatSuggestions}
              layerNames={layerNames}
              onAddPointsToMap={onAddPointsToMap}
            />
          ) : (
            <div className="px-4 py-3 text-xs text-muted">
              Drop a CSV to begin. You&apos;ll be able to ask spatial questions immediately — no need to run a workflow first.
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

function Section({ title, children, tight }: { title: string; children: ReactNode; tight?: boolean }) {
  return (
    <div className={`${tight ? "px-4 py-2" : "px-4 py-3"} border-b border-border`}>
      <div className="text-[10px] uppercase tracking-wider text-muted mb-2">{title}</div>
      {children}
    </div>
  );
}
