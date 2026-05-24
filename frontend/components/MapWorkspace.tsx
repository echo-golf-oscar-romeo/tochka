"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import MapCanvas, { type MapCanvasHandle } from "./MapCanvas";
import Toolkit, { type Workflow } from "./Toolkit";
import UploadDialog from "./UploadDialog";
import ChatPanel from "./ChatPanel";
import { analyzeStream, beautifyOnce, fetchStorymap } from "@/lib/api";
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

  const [networkId, setNetworkId] = useState<string | null>(null);
  const [layers, setLayers] = useState<StoryLayer[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [activeWorkflow, setActiveWorkflow] = useState<Workflow | null>(null);
  const [busy, setBusy] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [beautifying, setBeautifying] = useState(false);
  const [beautifyLog, setBeautifyLog] = useState<BeautifyLog[]>([]);
  const [storymapId, setStorymapId] = useState<string | null>(null);

  // ----- Upload -----
  const handleUploaded = useCallback((id: string) => {
    setNetworkId(id);
    setLayers([]);            // clear previous run's layers
    setEvents([]);
    setStorymapId(null);
    setShowUpload(false);
    // Pre-render the points immediately by asking /analyze for layer events
    // — but we don't have a fast preview endpoint; instead we just wait for
    // the user to pick a workflow. The first layer_added event during any
    // workflow will reveal the network.
  }, []);

  // ----- Run a workflow -----
  const handleWorkflow = useCallback(async (workflow: Workflow) => {
    if (!networkId || busy) return;
    setActiveWorkflow(workflow);
    setBusy(true);
    setLayers([]);
    setEvents([]);
    setStorymapId(null);
    const abort = new AbortController();
    try {
      await analyzeStream(
        { network_id: networkId, archetypes: ARCHETYPE_BY_WORKFLOW[workflow] },
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
  }, [networkId, busy]);

  // ----- Beautify loop -----
  const handleBeautify = useCallback(async () => {
    if (!mapHandleRef.current || busy || beautifying) return;
    const iterationMax = 3;
    setBeautifying(true);
    setBeautifyLog([]);
    try {
      // Snapshot current paint properties from the layer prop set; the backend
      // doesn't need MapLibre's internal state, just what we set when adding.
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

        // Apply via MapLibre's setPaintProperty (no React re-render needed).
        mapHandleRef.current.applyPaintUpdates(result.updates);
        // Mirror updates into local style state so the next iteration sees them.
        currentStyles = currentStyles.map((s) => {
          const u = result.updates.find((x) => x.layer_id === s.layer_id);
          if (!u) return s;
          return { ...s, paint: { ...(s.paint as Record<string, unknown>), ...u.paint } };
        });

        // Small pause so the user sees one change at a time.
        await new Promise((r) => setTimeout(r, 600));
      }
    } catch (e) {
      console.error("beautify failed:", e);
    } finally {
      setBeautifying(false);
    }
  }, [busy, beautifying, layers]);

  // ----- Open storymap -----
  const handleOpenStorymap = useCallback(async () => {
    if (!storymapId) return;
    // Verify the storymap exists server-side, then navigate.
    try {
      await fetchStorymap(storymapId);
      router.push(`/story/${storymapId}`);
    } catch (e) {
      console.error("storymap fetch failed:", e);
    }
  }, [storymapId, router]);

  // Synthesise an "agent progress" line for the bottom of the screen.
  const lastInteresting = lastInterestingEvent(events);

  return (
    <main className="h-screen w-screen flex overflow-hidden bg-paper">
      <Toolkit
        networkId={networkId}
        activeWorkflow={activeWorkflow}
        busy={busy}
        beautifying={beautifying}
        onUpload={() => setShowUpload(true)}
        onRunWorkflow={handleWorkflow}
        onBeautify={handleBeautify}
        onOpenStorymap={handleOpenStorymap}
        storymapReady={Boolean(storymapId)}
      />

      <div className="relative flex-1 h-full">
        <MapCanvas
          ref={mapHandleRef}
          layers={layers}
          autoFit
        />

        {/* Empty state */}
        {!networkId && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="pointer-events-auto max-w-md text-center bg-white/95 backdrop-blur rounded-xl shadow-lg px-8 py-7 border border-muted/30">
              <h1 className="font-serif text-3xl mb-2">Tochka</h1>
              <p className="text-sm text-muted mb-5">
                Drop a CSV of locations on the map.
                Run Diagnose / Expand / Rationalise. Ask follow-ups on the right.
              </p>
              <button
                type="button"
                onClick={() => setShowUpload(true)}
                className="rounded bg-accent text-white px-5 py-2 text-sm"
              >
                Upload network CSV
              </button>
            </div>
          </div>
        )}

        {/* Progress strip */}
        {(busy || lastInteresting) && (
          <div className="absolute left-4 bottom-4 z-10 max-w-md bg-white/95 backdrop-blur rounded shadow-md border border-muted/30 px-3 py-2 text-xs">
            <div className="flex items-center gap-2">
              {busy && (
                <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
              )}
              <span className="text-ink">{lastInteresting ?? "Ready."}</span>
            </div>
            {beautifyLog.length > 0 && (
              <ul className="mt-2 space-y-0.5 text-[11px] text-muted">
                {beautifyLog.map((b) => (
                  <li key={b.iteration}>
                    <span className="font-medium text-warm">·</span> iter {b.iteration}:{" "}
                    <span className="text-ink/80">{b.notes}</span>
                    {b.provider && <span className="ml-1 text-[10px]">({b.provider})</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Chat is always available, with a button at bottom-right when closed. */}
      {storymapId ? (
        <ChatPanel storymapId={storymapId} initialOpen={false} />
      ) : null}

      {showUpload && (
        <UploadDialog onUploaded={handleUploaded} onClose={() => setShowUpload(false)} />
      )}
    </main>
  );
}


function lastInterestingEvent(events: AgentEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev.kind === "thought") return String(ev.payload?.text ?? "");
    if (ev.kind === "tool_call") return `running ${ev.payload?.tool}…`;
    if (ev.kind === "tool_result") return `← ${ev.payload?.tool}`;
    if (ev.kind === "narrating") return `writing "${ev.payload?.title ?? ev.payload?.section_id}"…`;
    if (ev.kind === "storymap_ready") return "Storymap ready.";
    if (ev.kind === "done") return "Done.";
  }
  return null;
}
