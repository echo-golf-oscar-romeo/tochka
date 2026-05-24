"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Header from "./Header";
import MapCanvas, { type MapCanvasHandle } from "./MapCanvas";
import UploadDialog from "./UploadDialog";
import WorkspacePanel, { type Workflow } from "./WorkspacePanel";
import { analyzeStream, beautifyOnce, fetchStorymap, type UploadResponse } from "@/lib/api";
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

  // ----- Layer toggle -----
  const handleToggleLayer = useCallback((id: string, visible: boolean) => {
    setLayerVisibility((prev) => ({ ...prev, [id]: visible }));
  }, []);

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
      />
      <main className="flex-1 min-h-0 flex">
        <div className="relative flex-1 min-w-0 no-logo">
          <MapCanvas
            ref={mapHandleRef}
            layers={layers}
            visibility={layerVisibility}
            autoFit
          />

          {/* Empty state */}
          {!network && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="pointer-events-auto max-w-md text-center bg-canvas/95 backdrop-blur rounded-xl shadow-soft px-7 py-6 border border-border">
                <h1 className="text-2xl font-semibold mb-2">Tochka</h1>
                <p className="text-sm text-muted mb-5">
                  Drop a CSV of locations. Pick a workflow.
                  Ask the data anything spatial.
                </p>
                <button
                  type="button"
                  onClick={() => setShowUpload(true)}
                  className="rounded bg-accent-500 hover:bg-accent-600 text-white px-5 py-2 text-sm font-medium"
                >
                  Upload network CSV
                </button>
              </div>
            </div>
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

        <WorkspacePanel
          networkId={network?.id ?? null}
          networkSummary={networkSummary}
          onUpload={() => setShowUpload(true)}
          activeWorkflow={activeWorkflow}
          busy={busy}
          onRunWorkflow={handleWorkflow}
          layers={layers}
          layerVisibility={layerVisibility}
          onToggleLayer={handleToggleLayer}
          storymapReady={Boolean(storymapId)}
          onOpenStorymap={handleOpenStorymap}
          beautifying={beautifying}
          onBeautify={handleBeautify}
          storymapIdForChat={storymapId}
          chatSuggestions={chatSuggestions}
        />
      </main>

      {showUpload && (
        <UploadDialog onUploaded={handleUploaded} onClose={() => setShowUpload(false)} />
      )}
    </div>
  );
}

// ---------- helpers ----------

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
      "circle-color": "#2f55e6",
      "circle-radius": 7,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 1.5,
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
    if (ev.kind === "thought") return String(ev.payload?.text ?? "");
    if (ev.kind === "tool_call") return `running ${ev.payload?.tool}…`;
    if (ev.kind === "tool_result") return `← ${ev.payload?.tool}`;
    if (ev.kind === "narrating") return `writing "${ev.payload?.title ?? ev.payload?.section_id}"…`;
    if (ev.kind === "storymap_ready") return "storymap ready";
    if (ev.kind === "done") return "done";
  }
  return null;
}
