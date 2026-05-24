"use client";

import type { Layer as StoryLayer } from "@/lib/storymap";

interface Props {
  layers: StoryLayer[];
  visibility: Record<string, boolean>;
  onToggle: (layerId: string, visible: boolean) => void;
}

const LAYER_LABELS: Record<string, string> = {
  "user-network": "Your network",
  "isochrones": "10-min walking catchments",
  "competitors": "HK competitor banks",
  "anomalies-under": "Under-performing branches",
};

export default function LayersList({ layers, visibility, onToggle }: Props) {
  if (layers.length === 0) {
    return (
      <p className="text-xs text-muted px-1 py-2">
        Layers will appear here as the agent runs.
      </p>
    );
  }
  return (
    <ul className="space-y-0.5">
      {layers.map((layer) => {
        const visible = visibility[layer.id] !== false;
        const count = featureCount(layer);
        const label = LAYER_LABELS[layer.id] ?? layer.id;
        const swatch = layerSwatch(layer);
        return (
          <li
            key={layer.id}
            className="group flex items-center gap-2 py-1.5 px-1 rounded hover:bg-rule"
          >
            <button
              type="button"
              onClick={() => onToggle(layer.id, !visible)}
              aria-pressed={visible}
              className="flex items-center gap-2 flex-1 text-left"
            >
              <span
                className={`inline-block h-3 w-3 rounded-sm border ${
                  visible ? "" : "opacity-30"
                }`}
                style={{ background: swatch.fill, borderColor: swatch.stroke }}
                aria-hidden
              />
              <span className={`text-sm ${visible ? "text-ink" : "text-subtle line-through"}`}>
                {label}
              </span>
              <span className="text-[11px] text-muted">{count}</span>
            </button>
            <span className="text-[10px] text-subtle opacity-0 group-hover:opacity-100">
              {visible ? "hide" : "show"}
            </span>
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
  const fill =
    (paint["fill-color"] as string) ??
    (paint["circle-color"] as string) ??
    (paint["line-color"] as string) ??
    "#0a0a0a";
  return { fill, stroke: "rgba(0,0,0,0.2)" };
}
