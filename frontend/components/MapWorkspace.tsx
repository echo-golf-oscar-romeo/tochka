"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ChatPanel from "./ChatPanel";
import Header from "./Header";
import MapCanvas, { type MapCanvasHandle } from "./MapCanvas";
import MethodologyPopover, { type Plan } from "./MethodologyPopover";
import UploadDialog from "./UploadDialog";
import WorkspacePanel, { type Workflow } from "./WorkspacePanel";
import { analyzeStream, beautifyOnce, fetchStorymap, uploadCsv, type UploadResponse } from "@/lib/api";
import type { Layer as StoryLayer } from "@/lib/storymap";

type AgentEvent = { kind: string; payload: Record<string, unknown> };

interface BeautifyLog {
  iteration: number;
  notes: string;
  provider?: string;
}

const ARCHETYPE_BY_WORKFLOW: Record<Workflow, ("diagnose" | "expand" | "rationalise")[]> = {
  diagnose: ["diagnose"],
  expand: ["expand"],
  rationalise: ["rationalise"],
};

// 8-colour rotating palette for chat-driven layers. Mirrors the
// theme.colors.layer.0..7 entries in tailwind.config.ts.
const LAYER_PALETTE = [
  "#FAD037", "#FB3640", "#FA37B2", "#C637FA",
  "#37B2FA", "#37FADD", "#37FA7E", "#FA8237",
];

export default function MapWorkspace() {
  const router = useRouter();
  const mapHandleRef = useRef<MapCanvasHandle | null>(null);

  const [network, setNetwork] = useState<UploadResponse | null>(null);
  const [layers, setLayers] = useState<StoryLayer[]>([]);
  const [layerVisibility, setLayerVisibility] = useState<Record<string, boolean>>({});
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [activeWorkflow, setActiveWorkflow] = useState<Workflow | null>(null);
  const [busy, setBusy] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [beautifying, setBeautifying] = useState(false);
  const [beautifyLog, setBeautifyLog] = useState<BeautifyLog[]>([]);
  const [storymapId, setStorymapId] = useState<string | null>(null);

  // Methodology popover state: filled in by plan_narrative / tool_* events.
  const [plan, setPlan] = useState<Plan | null>(null);
  const [currentTool, setCurrentTool] = useState<string | null>(null);
  const [completedTools, setCompletedTools] = useState<Set<string>>(new Set());
  const [planDone, setPlanDone] = useState(false);

  // ----- Upload -----
  const handleUploaded = useCallback((net: UploadResponse) => {
    setNetwork(net);
    setStorymapId(null);
    setEvents([]);
    setBeautifyLog([]);
    setShowUpload(false);

    // Pre-render the user network so points appear immediately.
    const preLayer = buildUserNetworkLayer(net);
    setLayers([preLayer]);
    setLayerVisibility({ [preLayer.id]: true });
  }, []);

  // ----- Run a workflow -----
  const handleWorkflow = useCallback(async (workflow: Workflow) => {
    if (!network || busy) return;
    setActiveWorkflow(workflow);
    setBusy(true);
    setEvents([]);
    setStorymapId(null);
    // Reset methodology tracker so the popover shows the new run from scratch.
    setPlan(null);
    setCurrentTool(null);
    setCompletedTools(new Set());
    setPlanDone(false);
    // Keep the user-network layer visible; clear analysis layers.
    setLayers((prev) => prev.filter((l) => l.id === "user-network"));
    const abort = new AbortController();
    try {
      await analyzeStream(
        { network_id: network.id, archetypes: ARCHETYPE_BY_WORKFLOW[workflow] },
        (ev) => {
          if (abort.signal.aborted) return;
          setEvents((prev) => [...prev, ev]);
          if (ev.kind === "layer_added") {
            const layer = (ev.payload?.layer ?? null) as StoryLayer | null;
            if (layer) {
              setLayers((prev) => {
                const idx = prev.findIndex((l) => l.id === layer.id);
                if (idx === -1) return [...prev, layer];
                const copy = prev.slice();
                copy[idx] = layer;
                return copy;
              });
              setLayerVisibility((prev) => ({ ...prev, [layer.id]: prev[layer.id] !== false }));
            }
          }
          if (ev.kind === "storymap_ready") {
            const sid = ev.payload?.storymap_id as string | undefined;
            if (sid) setStorymapId(sid);
            setPlanDone(true);
          }
          if (ev.kind === "plan_narrative") {
            const text = String(ev.payload?.text ?? "");
            const archetypes = (ev.payload?.archetypes as string[] | undefined) ?? [];
            const tool_sequence = (ev.payload?.tool_sequence as string[] | undefined) ?? [];
            setPlan({ text, archetypes, tool_sequence });
          }
          if (ev.kind === "tool_call") {
            const tool = ev.payload?.tool as string | undefined;
            if (tool) setCurrentTool(tool);
          }
          if (ev.kind === "tool_result") {
            const tool = ev.payload?.tool as string | undefined;
            if (tool) {
              setCompletedTools((prev) => {
                if (prev.has(tool)) return prev;
                const next = new Set(prev);
                next.add(tool);
                return next;
              });
            }
          }
          if (ev.kind === "done") {
            setPlanDone(true);
            setCurrentTool(null);
          }
        },
        abort.signal,
      );
    } catch (e) {
      if ((e as Error)?.name !== "AbortError") {
        console.error("workflow failed:", e);
      }
    } finally {
      setBusy(false);
      setActiveWorkflow(null);
      setPlanDone(true);
      setCurrentTool(null);
    }
  }, [network, busy]);

  // ----- Beautify loop -----
  const handleBeautify = useCallback(async () => {
    if (!mapHandleRef.current || busy || beautifying) return;
    const iterationMax = 3;
    setBeautifying(true);
    setBeautifyLog([]);
    try {
      let currentStyles = layers.map((l) => ({
        layer_id: l.id,
        paint: (l.paint ?? {}) as Record<string, unknown>,
      }));
      for (let iter = 1; iter <= iterationMax; iter++) {
        const screenshot = mapHandleRef.current.screenshot();
        if (!screenshot) break;
        const result = await beautifyOnce({
          screenshot,
          styles: currentStyles,
          iteration: iter,
          iteration_max: iterationMax,
        });
        setBeautifyLog((prev) => [...prev, {
          iteration: iter,
          notes: result.notes,
          provider: result.provider ?? undefined,
        }]);
        if (!result.updates || result.updates.length === 0) break;
        mapHandleRef.current.applyPaintUpdates(result.updates);
        currentStyles = currentStyles.map((s) => {
          const u = result.updates.find((x) => x.layer_id === s.layer_id);
          if (!u) return s;
          return { ...s, paint: { ...(s.paint as Record<string, unknown>), ...u.paint } };
        });
        await new Promise((r) => setTimeout(r, 600));
      }
    } catch (e) {
      console.error("beautify failed:", e);
    } finally {
      setBeautifying(false);
    }
  }, [busy, beautifying, layers]);

  // ----- Layer toggle / remove -----
  const handleToggleLayer = useCallback((id: string, visible: boolean) => {
    setLayerVisibility((prev) => ({ ...prev, [id]: visible }));
  }, []);

  const handleRemoveLayer = useCallback((id: string) => {
    setLayers((prev) => prev.filter((l) => l.id !== id));
    setLayerVisibility((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, []);

  // ----- Chat → Map layer -----
  const chatLayerCountRef = useRef(0);
  const handleAddPointsToMap = useCallback((
    label: string,
    points: { id: string; lat: number; lng: number; label?: string }[],
  ) => {
    chatLayerCountRef.current += 1;
    const layerId = `chat-${chatLayerCountRef.current}`;
    const features = points.map((p) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [p.lng, p.lat] },
      properties: { id: p.id, name: p.label ?? "" },
    }));
    // Rotate through the 8-colour layer palette so each chat-driven layer
    // is visually distinct from the user network and from prior chat layers.
    const colour = LAYER_PALETTE[(chatLayerCountRef.current - 1) % LAYER_PALETTE.length];
    const layer: StoryLayer = {
      id: layerId,
      kind: "geojson",
      data: { type: "FeatureCollection", features },
      paint: {
        "circle-color": colour,
        "circle-radius": 6,
        "circle-stroke-color": "#FDFDFD",
        "circle-stroke-width": 2,
      },
      label,
    };
    setLayers((prev) => [...prev, layer]);
    setLayerVisibility((prev) => ({ ...prev, [layerId]: true }));
    // Silently record the label for the next layers list view
    chatLayerLabelsRef.current[layerId] = label;
  }, []);
  const chatLayerLabelsRef = useRef<Record<string, string>>({});

  // ----- Storymap -----
  const handleOpenStorymap = useCallback(async () => {
    if (!storymapId) return;
    try {
      await fetchStorymap(storymapId);
      router.push(`/story/${storymapId}`);
    } catch (e) {
      console.error("storymap fetch failed:", e);
    }
  }, [storymapId, router]);

  // ----- Derived: dataset-aware chat suggestions -----
  const chatSuggestions = useMemo(() => deriveSuggestions(network), [network]);
  const networkSummary = useMemo(() => deriveNetworkSummary(network), [network]);

  // Layer labels for the "/" autocomplete in chat.
  const layerNames = useMemo(() => layers.map((l) => l.id), [layers]);

  // Beautify result summary for the panel notice strip.
  const beautifyNotice = useMemo(() => {
    if (beautifyLog.length === 0) return null;
    const last = beautifyLog[beautifyLog.length - 1];
    return `${last.notes} (${last.provider ?? "vision"})`;
  }, [beautifyLog]);
  const lastEventLine = useMemo(() => lastInterestingLine(events), [events]);
  const headerStatus = useMemo(() => {
    if (beautifying) return "Beautifying";
    if (activeWorkflow) return `Running ${activeWorkflow}`;
    if (storymapId) return "Analysis ready";
    if (network) return "Loaded";
    return "Idle";
  }, [activeWorkflow, beautifying, storymapId, network]);

  return (
    <div className="h-screen w-screen flex flex-col bg-canvas text-ink">
      <Header
        status={headerStatus}
        detail={lastEventLine ?? undefined}
        busy={busy || beautifying}
        activeWorkflow={activeWorkflow}
        onRunWorkflow={handleWorkflow}
        workflowsDisabled={!network || busy}
      />
      <main className="flex-1 min-h-0 flex">
        {/* Left: chat (primary, bigger) */}
        <aside className="w-[28rem] shrink-0 border-r border-border bg-canvas flex flex-col h-full overflow-hidden">
          <div className="px-4 pt-3 pb-2 flex items-center justify-between border-b border-border">
            <div className="text-[10px] uppercase tracking-wider text-muted">Ask the data</div>
            <div className="text-[10px] text-subtle">
              {network ? "Spatial SQL · DuckDB" : "Upload first"}
            </div>
          </div>
          <div className="flex-1 min-h-0">
            {network ? (
              <ChatPanel
                storymapId={storymapId ?? undefined}
                networkId={network.id}
                suggestions={chatSuggestions}
                layerNames={layerNames}
                onAddPointsToMap={handleAddPointsToMap}
              />
            ) : (
              <div className="px-4 py-4 text-xs text-muted">
                Drop a CSV to begin. You&apos;ll be able to ask spatial questions immediately — no need to run a workflow first.
              </div>
            )}
          </div>
        </aside>

        {/* Center: map */}
        <div className="relative flex-1 min-w-0 no-logo">
          <MapCanvas
            ref={mapHandleRef}
            layers={layers}
            visibility={layerVisibility}
            autoFit
          />

          <MethodologyPopover
            plan={plan}
            currentTool={currentTool}
            completedTools={completedTools}
            done={planDone}
            onDismiss={() => setPlan(null)}
          />

          {/* Empty state — bright liquid-glass card; CSV can be dropped directly */}
          {!network && (
            <LandingCard
              onPickFile={() => setShowUpload(true)}
              onFileDropped={async (file) => {
                try {
                  const net = await uploadCsv(file);
                  handleUploaded(net);
                } catch (e) {
                  console.error("upload failed:", e);
                }
              }}
            />
          )}

          {/* Progress strip */}
          {(busy || beautifyLog.length > 0) && (
            <div className="absolute left-4 bottom-4 z-10 max-w-md bg-canvas/95 backdrop-blur rounded shadow-soft border border-border px-3 py-2 text-xs">
              <div className="flex items-center gap-2">
                {busy && (
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-500 animate-pulse" />
                )}
                <span className="text-ink">{lastEventLine ?? "Ready."}</span>
              </div>
              {beautifyLog.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-[11px] text-muted">
                  {beautifyLog.map((b) => (
                    <li key={b.iteration}>
                      <span className="text-accent-600">·</span> iter {b.iteration}:{" "}
                      <span className="text-ink/80">{b.notes}</span>
                      {b.provider && <span className="ml-1 text-[10px]">({b.provider})</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* Right: layers + outputs */}
        <WorkspacePanel
          networkId={network?.id ?? null}
          networkSummary={networkSummary}
          onUpload={() => setShowUpload(true)}
          busy={busy}
          layers={layers}
          layerVisibility={layerVisibility}
          onToggleLayer={handleToggleLayer}
          onRemoveLayer={handleRemoveLayer}
          storymapReady={Boolean(storymapId)}
          onOpenStorymap={handleOpenStorymap}
          beautifying={beautifying}
          onBeautify={handleBeautify}
          beautifyNotice={beautifyNotice}
        />
      </main>

      {showUpload && (
        <UploadDialog onUploaded={handleUploaded} onClose={() => setShowUpload(false)} />
      )}
    </div>
  );
}

// ---------- helpers ----------

interface LandingCardProps {
  onPickFile: () => void;
  onFileDropped: (file: File) => void;
}

function LandingCard({ onPickFile, onFileDropped }: LandingCardProps) {
  const [dragging, setDragging] = useState(false);
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      <div
        className={`pointer-events-auto max-w-lg text-center liquid-glass-strong rounded-2xl px-10 py-9 transition ${
          dragging ? "ring-2 ring-accent-500" : ""
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files?.[0];
          if (f) onFileDropped(f);
        }}
      >
        <div className="text-5xl text-ink mb-2 leading-none font-semibold tracking-tightish lowercase">
          tochka
        </div>
        <p className="text-sm text-ink/80 mb-6 leading-relaxed max-w-sm mx-auto">
          Spatial intelligence for Hong Kong. Drop a CSV of locations here — or click below — to start. Then run a workflow or ask the data anything spatial.
        </p>
        <div className="flex items-center justify-center gap-2">
          <label className="cursor-pointer rounded-full accent-gradient text-canvas px-5 py-2 text-sm font-medium shadow-soft hover:shadow-pop transition">
            Upload network CSV
            <input
              type="file"
              accept=".csv,.tsv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onFileDropped(f);
              }}
            />
          </label>
          <button
            type="button"
            onClick={onPickFile}
            className="rounded-full border border-border text-ink hover:border-accent-300 px-4 py-2 text-sm transition bg-canvas/60"
          >
            Options…
          </button>
          <a
            href="/about"
            className="rounded-full border border-border text-ink hover:border-accent-300 px-4 py-2 text-sm transition bg-canvas/60"
          >
            What is this?
          </a>
        </div>
        <p className="mt-4 text-[11px] text-muted">
          {dragging ? "release to upload" : "drag a .csv anywhere on this card"}
        </p>
      </div>
    </div>
  );
}

function buildUserNetworkLayer(net: UploadResponse): StoryLayer {
  const features = net.locations
    .filter((loc) => loc.lat !== null && loc.lng !== null)
    .map((loc) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [loc.lng!, loc.lat!] },
      properties: { id: loc.id, name: loc.name },
    }));
  return {
    id: "user-network",
    kind: "geojson",
    data: { type: "FeatureCollection", features },
    paint: {
      "circle-color": "#4F35F8",
      "circle-radius": 7,
      "circle-stroke-color": "#FDFDFD",
      "circle-stroke-width": 2,
    },
  };
}


function deriveNetworkSummary(net: UploadResponse | null): string | null {
  if (!net) return null;
  return `${net.locations.length} locations · ${net.source_filename}`;
}


function deriveSuggestions(net: UploadResponse | null): string[] {
  if (!net || net.locations.length === 0) return [];
  const first = net.locations.find((l) => l.name) || net.locations[0];
  const second = net.locations.find((l) => l.id !== first.id && l.name);
  const out = [
    `Which 10 competitor banks are closest to ${first.name}?`,
    `Show all branches with their nearest competitor distance.`,
    `How many competitor banks sit within 500m of each of my branches?`,
  ];
  if (second) {
    out.push(`Compare ${first.name} and ${second.name}: catchment population and competitor count.`);
  }
  return out;
}


function lastInterestingLine(events: AgentEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev.kind === "plan_narrative") return String(ev.payload?.text ?? "");
    if (ev.kind === "thought") return String(ev.payload?.text ?? "");
    if (ev.kind === "tool_call") return `running ${ev.payload?.tool}…`;
    if (ev.kind === "tool_result") return `← ${ev.payload?.tool}`;
    if (ev.kind === "narrating") return `writing "${ev.payload?.title ?? ev.payload?.section_id}"…`;
    if (ev.kind === "storymap_ready") return "storymap ready";
    if (ev.kind === "done") return "done";
  }
  return null;
}
