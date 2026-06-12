"use client";

import { useRef, useState } from "react";
import { Eye, EyeOff, GripVertical, Trash2 } from "lucide-react";
import type { Layer as StoryLayer } from "@/lib/storymap";

interface Props {
  layers: StoryLayer[];
  visibility: Record<string, boolean>;
  onToggle: (layerId: string, visible: boolean) => void;
  onRemove?: (layerId: string) => void;
  /** Called with the full id list in its new order after a drag. Following
   *  the Figma/Mapbox-Studio convention, the FIRST id in the list renders
   *  on TOP of the map stack (MapCanvas.applyOrder enforces this). */
  onReorder?: (nextOrder: string[]) => void;
}

const LAYER_LABELS: Record<string, string> = {
  "user-network": "Your network",
  "isochrones": "10-min walking catchments",
  "competitors": "HK competitor banks",
  "anomalies-under": "Under-performing branches",
  "cannibalisation": "Cannibalisation pairs (<800m)",
  "opportunity": "Opportunity hexes",
};

function deriveLabel(layer: StoryLayer): string {
  if (layer.label) return layer.label;
  if (LAYER_LABELS[layer.id]) return LAYER_LABELS[layer.id];
  if (layer.id.startsWith("chat-")) return `Chat result · ${layer.id.slice(5)}`;
  return layer.id;
}

export default function LayersList({ layers, visibility, onToggle, onRemove, onReorder }: Props) {
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const orderRef = useRef<string[]>([]);
  orderRef.current = layers.map((l) => l.id);

  if (layers.length === 0) {
    return (
      <p className="text-xs text-muted px-1 py-2">
        Layers appear here as analyses run. Toggle the eye to hide, drag the
        grip to restack, trash to remove.
      </p>
    );
  }

  function handleDrop(targetId: string) {
    if (!onReorder || !dragId || dragId === targetId) {
      setDragId(null); setOverId(null);
      return;
    }
    const order = [...orderRef.current];
    const from = order.indexOf(dragId);
    const to = order.indexOf(targetId);
    if (from === -1 || to === -1) { setDragId(null); setOverId(null); return; }
    order.splice(from, 1);
    order.splice(to, 0, dragId);
    onReorder(order);
    setDragId(null); setOverId(null);
  }

  return (
    <ul className="space-y-0.5">
      {layers.map((layer) => {
        const visible = visibility[layer.id] !== false;
        const count = featureCount(layer);
        const label = deriveLabel(layer);
        const swatch = layerSwatch(layer);
        const isDragging = dragId === layer.id;
        const isOver = overId === layer.id && dragId !== layer.id;
        return (
          <li
            key={layer.id}
            draggable={Boolean(onReorder)}
            onDragStart={(e) => {
              setDragId(layer.id);
              e.dataTransfer.effectAllowed = "move";
            }}
            onDragOver={(e) => { e.preventDefault(); setOverId(layer.id); }}
            onDragLeave={() => setOverId((cur) => (cur === layer.id ? null : cur))}
            onDrop={(e) => { e.preventDefault(); handleDrop(layer.id); }}
            onDragEnd={() => { setDragId(null); setOverId(null); }}
            className={`group fade-in-up flex items-center gap-1.5 py-1.5 px-1.5 rounded-md transition-all duration-150 ${
              isDragging ? "opacity-40 scale-[0.98]" : "hover:bg-rule"
            } ${isOver ? "ring-1 ring-accent-400 bg-accent-50" : ""}`}
          >
            {onReorder && (
              <span
                className="text-subtle opacity-0 group-hover:opacity-100 cursor-grab active:cursor-grabbing transition-opacity shrink-0"
                aria-hidden
              >
                <GripVertical size={13} />
              </span>
            )}
            <span
              className={`inline-block h-3 w-3 rounded-sm border shrink-0 transition-opacity duration-200 ${
                visible ? "" : "opacity-25"
              }`}
              style={{ background: swatch.fill, borderColor: swatch.stroke }}
              aria-hidden
            />
            <span
              className={`text-sm truncate flex-1 min-w-0 transition-colors duration-200 ${
                visible ? "text-ink" : "text-subtle"
              }`}
              title={label}
            >
              {label}
            </span>
            <span className="text-[11px] text-muted shrink-0 tabular-nums">{count}</span>
            <div className="flex items-center gap-0.5 shrink-0">
              <button
                type="button"
                onClick={() => onToggle(layer.id, !visible)}
                aria-pressed={visible}
                aria-label={visible ? `Hide ${label}` : `Show ${label}`}
                title={visible ? "Hide layer" : "Show layer"}
                className={`p-1 rounded-md transition-colors ${
                  visible
                    ? "text-muted hover:text-ink hover:bg-border/60"
                    : "text-subtle hover:text-ink hover:bg-border/60"
                }`}
              >
                {visible ? <Eye size={14} /> : <EyeOff size={14} />}
              </button>
              {onRemove && (
                <button
                  type="button"
                  onClick={() => onRemove(layer.id)}
                  aria-label={`Remove ${label}`}
                  title="Remove layer"
                  className="p-1 rounded-md text-subtle opacity-0 group-hover:opacity-100 hover:text-highlight-600 hover:bg-highlight-50 transition-all"
                >
                  <Trash2 size={13} />
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function featureCount(layer: StoryLayer): string {
  if (layer.kind === "geojson" && layer.data) {
    const n = (layer.data as GeoJSON.FeatureCollection).features?.length ?? 0;
    return `${n}`;
  }
  return "";
}

function layerSwatch(layer: StoryLayer): { fill: string; stroke: string } {
  const paint = (layer.paint ?? {}) as Record<string, unknown>;
  const raw =
    paint["fill-color"] ?? paint["circle-color"] ?? paint["line-color"] ?? "#0A0903";
  // Data-driven paint (interpolate/match arrays) → neutral multi swatch.
  const fill = typeof raw === "string" ? raw : "conic-gradient(from 0deg, #FAD037, #FB3640, #C637FA, #37B2FA, #FAD037)";
  return { fill, stroke: "rgba(10,9,3,0.2)" };
}
