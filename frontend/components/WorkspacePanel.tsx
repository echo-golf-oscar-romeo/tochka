"use client";

import { type ReactNode } from "react";
import LayersList from "./LayersList";
import type { Layer as StoryLayer } from "@/lib/storymap";

export type Workflow = "diagnose" | "expand" | "rationalise";

interface Props {
  // Data
  networkId: string | null;
  networkSummary: string | null;
  onUpload: () => void;

  // Busy state (workflows are now triggered from the Header)
  busy: boolean;

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
}

export default function WorkspacePanel(props: Props) {
  const {
    networkId, networkSummary, onUpload,
    busy,
    layers, layerVisibility, onToggleLayer, onRemoveLayer,
    storymapReady, onOpenStorymap, beautifying, onBeautify, beautifyNotice,
  } = props;
  const disabled = !networkId || busy;

  return (
    <aside className="w-[22rem] shrink-0 border-l border-border bg-canvas flex flex-col h-full overflow-hidden">
      {/* Data */}
      <Section title="Data">
        <button
          type="button"
          onClick={onUpload}
          className="w-full rounded border border-border hover:border-accent-400 hover:bg-accent-50 px-3 py-2 text-left transition"
        >
          <div className="text-sm font-medium text-ink">
            {networkId ? "Replace network" : "Upload network CSV"}
          </div>
          <div className="text-xs text-muted mt-0.5">
            {networkSummary ?? "Drag your locations to start"}
          </div>
        </button>
      </Section>

      {/* Layers — takes remaining vertical space */}
      <div className="flex-1 min-h-0 flex flex-col border-b border-border">
        <div className="px-4 pt-3 pb-2 flex items-center justify-between">
          <div className="text-[10px] uppercase tracking-wider text-muted">
            Layers {layers.length > 0 ? `· ${layers.length}` : ""}
          </div>
          <div className="text-[10px] text-subtle">
            {layers.length > 0 ? "click to toggle" : ""}
          </div>
        </div>
        <div className="flex-1 min-h-0 overflow-auto px-4 pb-3">
          {layers.length === 0 ? (
            <div className="text-xs text-muted py-2">
              No layers yet. Run an analysis from the header, or ask the chat to plot points.
            </div>
          ) : (
            <LayersList
              layers={layers}
              visibility={layerVisibility}
              onToggle={onToggleLayer}
              onRemove={onRemoveLayer}
            />
          )}
        </div>
      </div>

      {/* Outputs */}
      <Section title="Refinement & output" tight>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onBeautify}
            disabled={disabled || beautifying}
            className="rounded border border-border hover:border-accent-400 px-3 py-2 text-left text-sm disabled:opacity-40 disabled:cursor-not-allowed transition"
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
            className="rounded border border-border hover:border-accent-400 px-3 py-2 text-left text-sm disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            <div className="font-medium">Open storymap</div>
            <div className="text-[10px] text-muted mt-0.5">
              {storymapReady ? "Five-section narrative" : "Run an analysis first"}
            </div>
          </button>
        </div>
      </Section>

      {beautifyNotice && (
        <div className="px-4 py-2 border-t border-border bg-highlight-50 text-[11px] text-ink">
          <span className="font-medium">Beautify:</span> {beautifyNotice}
        </div>
      )}
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
