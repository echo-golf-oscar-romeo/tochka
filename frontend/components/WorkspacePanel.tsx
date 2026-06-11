"use client";

import { type ReactNode } from "react";
import { FileText, Trash2, UploadCloud } from "lucide-react";
import LayersList from "./LayersList";
import type { Layer as StoryLayer } from "@/lib/storymap";

export type Workflow = "diagnose" | "expand" | "rationalise";

export interface SavedReportMeta {
  id: string;
  title: string;
  createdAt: string;
}

interface Props {
  // Data
  networkId: string | null;
  networkSummary: string | null;
  onUpload: () => void;

  // Busy state (workflows are triggered from the Header / question flow)
  busy: boolean;

  // Layers
  layers: StoryLayer[];
  layerVisibility: Record<string, boolean>;
  onToggleLayer: (id: string, visible: boolean) => void;
  onRemoveLayer: (id: string) => void;
  onReorderLayers?: (nextOrder: string[]) => void;

  // Reports
  reportReady: boolean;
  onOpenReport: () => void;
  savedReports: SavedReportMeta[];
  onOpenSavedReport: (id: string) => void;
  onDeleteSavedReport: (id: string) => void;
}

export default function WorkspacePanel(props: Props) {
  const {
    networkId, networkSummary, onUpload,
    layers, layerVisibility, onToggleLayer, onRemoveLayer, onReorderLayers,
    reportReady, onOpenReport, savedReports, onOpenSavedReport, onDeleteSavedReport,
  } = props;

  return (
    <aside className="w-[22rem] shrink-0 border-l border-border bg-canvas flex flex-col h-full overflow-hidden">
      {/* Data */}
      <Section title="Data">
        <button
          type="button"
          onClick={onUpload}
          className="w-full rounded-lg border border-border hover:border-accent-400 hover:bg-accent-50 px-3 py-2 text-left transition-all duration-200 flex items-start gap-2.5"
        >
          <UploadCloud size={16} className="text-accent-500 mt-0.5 shrink-0" />
          <span className="min-w-0">
            <span className="block text-sm font-medium text-ink">
              {networkId ? "Replace network" : "Upload network CSV"}
            </span>
            <span className="block text-xs text-muted mt-0.5 truncate">
              {networkSummary ?? "Drag your locations to start"}
            </span>
          </span>
        </button>
      </Section>

      {/* Layers — takes remaining vertical space */}
      <div className="flex-1 min-h-0 flex flex-col border-b border-border">
        <div className="px-4 pt-3 pb-2 flex items-center justify-between">
          <div className="text-[10px] uppercase tracking-wider text-muted">
            Layers {layers.length > 0 ? `· ${layers.length}` : ""}
          </div>
          <div className="text-[10px] text-subtle">
            {layers.length > 0 ? "top of list = top of map" : ""}
          </div>
        </div>
        <div className="flex-1 min-h-0 overflow-auto px-4 pb-3">
          {layers.length === 0 ? (
            <div className="text-xs text-muted py-2">
              No layers yet. Ask the chat anything spatial, or run an analysis.
            </div>
          ) : (
            <LayersList
              layers={layers}
              visibility={layerVisibility}
              onToggle={onToggleLayer}
              onRemove={onRemoveLayer}
              onReorder={onReorderLayers}
            />
          )}
        </div>
      </div>

      {/* Reports */}
      <Section title={`Reports ${savedReports.length > 0 ? `· ${savedReports.length}` : ""}`} tight>
        <button
          type="button"
          onClick={onOpenReport}
          disabled={!reportReady}
          className="w-full rounded-lg border border-border hover:border-accent-400 hover:bg-accent-50 px-3 py-2 text-left text-sm disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 flex items-start gap-2.5"
        >
          <FileText size={16} className="text-accent-500 mt-0.5 shrink-0" />
          <span>
            <span className="block font-medium text-ink">Open report</span>
            <span className="block text-[10px] text-muted mt-0.5">
              {reportReady ? "Charts, KPIs & recommendations" : "Run an analysis first"}
            </span>
          </span>
        </button>

        {savedReports.length > 0 && (
          <ul className="mt-2 space-y-0.5 max-h-36 overflow-y-auto">
            {savedReports.map((r) => (
              <li key={r.id} className="group flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-rule transition-colors">
                <button
                  type="button"
                  onClick={() => onOpenSavedReport(r.id)}
                  className="flex-1 min-w-0 text-left"
                  title={r.title}
                >
                  <span className="block text-[12px] text-ink truncate">{r.title}</span>
                  <span className="block text-[10px] text-subtle">
                    {new Date(r.createdAt).toLocaleDateString("en-HK", { day: "numeric", month: "short" })}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => onDeleteSavedReport(r.id)}
                  aria-label={`Delete report ${r.title}`}
                  className="p-1 rounded-md text-subtle opacity-0 group-hover:opacity-100 hover:text-highlight-600 hover:bg-highlight-50 transition-all"
                >
                  <Trash2 size={12} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </aside>
  );
}

function Section({ title, children, tight }: { title: string; children: ReactNode; tight?: boolean }) {
  return (
    <div className={`${tight ? "px-4 py-2.5" : "px-4 py-3"} border-b border-border`}>
      <div className="text-[10px] uppercase tracking-wider text-muted mb-2">{title}</div>
      {children}
    </div>
  );
}
