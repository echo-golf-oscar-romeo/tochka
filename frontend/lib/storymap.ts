// Mirrors backend/app/models/storymap.py. Keep these in sync by hand for now;
// codegen later if the API surface grows.

export interface MapLocation {
  center: [number, number]; // lng, lat
  zoom: number;
  pitch?: number;
  bearing?: number;
}

export interface LayerOp {
  layer: string;
  opacity: number;
}

export interface Layer {
  id: string;
  kind: "geojson" | "raster" | "vector" | "hex";
  data?: GeoJSON.FeatureCollection | null;
  source_url?: string | null;
  paint?: Record<string, unknown>;
  /** Optional human-readable name used by the right-hand layers panel.
   *  Set by client-side layer creation (chat → map). Layers from the
   *  backend leave this undefined and fall back to id-keyed labels. */
  label?: string | null;
}

export interface StorymapSection {
  id: string;
  title: string;
  description: string;
  alignment?: "left" | "center" | "right" | "full";
  location: MapLocation;
  on_enter?: LayerOp[];
  on_exit?: LayerOp[];
  callouts?: string[];
  kpis?: Record<string, string>;
}

export interface StorymapResult {
  id: string;
  network_id: string;
  style_url: string;
  layers: Layer[];
  sections: StorymapSection[];
  summary?: string | null;
}
