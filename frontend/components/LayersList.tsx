"use client";

import type { Layer as StoryLayer } from "@/lib/storymap";

interface Props {
  layers: StoryLayer[];
  visibility: Record<string, boolean>;
  onToggle: (layerId: string, visible: boolean) => void;
  onRemove?: (layerId: string) => void;
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

export default function LayersList({ layers, visibility, onToggle, onRemove }: Props) {
  if (layers.length === 0) {
    return (
      <p className="text-xs text-muted px-1 py-2">
        Layers appear here as workflows produce them. Toggle to hide / show. Remove to free the canvas.
      </p>
    );
  }
  return (
    <ul className="space-y-0.5">
      {layers.map((layer) => {
        const visible = visibility[layer.id] !== false;
        const count = featureCount(layer);
        const label = deriveLabel(layer);
        const swatch = layerSwatch(layer);
        return (
          <li
            key={layer.id}
            className="group flex items-center gap-2 py-1.5 px-1.5 rounded hover:bg-rule transition"
          >
            <button
              type="button"
              onClick={() => onToggle(layer.id, !visible)}
              aria-pressed={visible}
              className="flex items-center gap-2 flex-1 text-left min-w-0"
            >
              <span
                className={`inline-block h-3 w-3 rounded-sm border shrink-0 ${
                  visible ? "" : "opacity-30"
                }`}
                style={{ background: swatch.fill, borderColor: swatch.stroke }}
                aria-hidden
              />
              <span className={`text-sm truncate ${visible ? "text-ink" : "text-subtle line-through"}`}>
                {label}
              </span>
              <span className="text-[11px] text-muted shrink-0">{count}</span>
            </button>
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
              <button
                type="button"
                onClick={() => onToggle(layer.id, !visible)}
                className="text-[10px] text-muted hover:text-ink px-1.5 py-0.5 rounded"
                title={visible ? "Hide layer" : "Show layer"}
              >
                {visible ? "hide" : "show"}
              </button>
              {onRemove && (
                <button
                  type="button"
                  onClick={() => onRemove(layer.id)}
                  className="text-muted hover:text-accent-700 transition rounded px-1.5 py-0.5"
                  title="Remove layer"
                  aria-label={`Remove ${label}`}
                >
                  <TrashIcon />
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}


function TrashIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
      <path d="M3 4h10M6 4V2.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 .5.5V4M5 4l.6 9.1a.5.5 0 0 0 .5.4h3.8a.5.5 0 0 0 .5-.4L11 4M7 7v4M9 7v4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
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
  const fill =
    (paint["fill-color"] as string) ??
    (paint["circle-color"] as string) ??
    (paint["line-color"] as string) ??
    "#0a0a0a";
  return { fill, stroke: "rgba(0,0,0,0.2)" };
}
