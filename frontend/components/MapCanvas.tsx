"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import maplibregl, { type Map as MlMap, type StyleSpecification } from "maplibre-gl";
import { csdiStyleUrl } from "@/lib/mapStyle";
import type { Layer as StoryLayer } from "@/lib/storymap";

export interface MapCanvasHandle {
  map: () => MlMap | null;
  /** Capture the current visible map as a PNG data URI (for vision agents). */
  screenshot: () => string | null;
  /** Apply MapLibre paint property updates to existing layers. */
  applyPaintUpdates: (updates: { layer_id: string; paint: Record<string, unknown> }[]) => void;
}

interface Props {
  layers: StoryLayer[];
  initialCenter?: [number, number];
  initialZoom?: number;
  styleUrl?: string;
  /** Auto-fit the view to the union of all geojson layers when they arrive. */
  autoFit?: boolean;
  /** Per-layer visibility flags. Missing entry = visible. */
  visibility?: Record<string, boolean>;
}

const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "bg", type: "background", paint: { "background-color": "#f6f4ef" } }],
};

const MapCanvas = forwardRef<MapCanvasHandle, Props>(function MapCanvas(
  { layers, initialCenter = [114.165, 22.33], initialZoom = 11, styleUrl, autoFit = true, visibility },
  ref,
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MlMap | null>(null);
  const loadedRef = useRef(false);
  const knownLayersRef = useRef<Set<string>>(new Set());
  const layersRef = useRef<StoryLayer[]>(layers);
  layersRef.current = layers;

  useImperativeHandle(ref, () => ({
    map: () => mapRef.current,
    screenshot: () => {
      const m = mapRef.current;
      if (!m) return null;
      // preserveDrawingBuffer would be cleaner but adds GPU overhead always;
      // we force a synchronous redraw first so the canvas is current.
      try {
        m.triggerRepaint();
        return m.getCanvas().toDataURL("image/png");
      } catch (e) {
        console.warn("screenshot failed:", e);
        return null;
      }
    },
    applyPaintUpdates: (updates) => {
      const m = mapRef.current;
      if (!m) return;
      for (const u of updates) {
        if (!m.getLayer(u.layer_id)) continue;
        for (const [prop, value] of Object.entries(u.paint)) {
          try {
            m.setPaintProperty(u.layer_id, prop, value as never);
          } catch (e) {
            console.warn(`setPaintProperty failed for ${u.layer_id}.${prop}:`, e);
          }
        }
      }
    },
  }), []);

  // ----- Init once -----
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: (styleUrl ?? csdiStyleUrl()) as unknown as StyleSpecification | string,
      center: initialCenter,
      zoom: initialZoom,
      attributionControl: { compact: true },
      preserveDrawingBuffer: true, // needed for screenshot capture
    });
    mapRef.current = map;

    map.on("error", () => {
      // If the remote style fails, fall back to a blank canvas so layers
      // still render on top — the dev overlay then becomes harmless.
      try { map.setStyle(FALLBACK_STYLE); } catch { /* ignore */ }
    });

    const reapply = () => {
      loadedRef.current = true;
      knownLayersRef.current.clear();
      for (const layer of layersRef.current) {
        addOrReplaceLayer(map, layer, knownLayersRef.current);
      }
      if (autoFit) fitToLayers(map, layersRef.current);
    };
    map.on("load", reapply);
    map.on("styledata", () => {
      if (loadedRef.current) reapply();
    });

    return () => {
      loadedRef.current = false;
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ----- Sync layers prop -> map -----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    const incoming = new Set(layers.map((l) => l.id));
    for (const layer of layers) {
      addOrReplaceLayer(map, layer, knownLayersRef.current);
    }
    for (const known of Array.from(knownLayersRef.current)) {
      if (!incoming.has(known) && !known.endsWith("-outline")) {
        removeLayer(map, known, knownLayersRef.current);
      }
    }
    applyVisibility(map, layers, visibility ?? {});
    if (autoFit) fitToLayers(map, layers);
  }, [layers, autoFit, visibility]);

  return <div ref={containerRef} className="w-full h-full" />;
});

export default MapCanvas;


function addOrReplaceLayer(map: MlMap, layer: StoryLayer, known: Set<string>) {
  if (layer.kind !== "geojson" || !layer.data) return;
  const data = layer.data as GeoJSON.FeatureCollection;
  // If source exists, just update the data; otherwise add fresh.
  const existing = map.getSource(layer.id) as maplibregl.GeoJSONSource | undefined;
  if (existing) {
    existing.setData(data);
    return;
  }
  map.addSource(layer.id, { type: "geojson", data });
  const sample = (data.features ?? [])[0]?.geometry?.type ?? "Point";
  const isPolygon = sample === "Polygon" || sample === "MultiPolygon";
  const isLine = sample === "LineString" || sample === "MultiLineString";
  const visual: "fill" | "line" | "circle" = isPolygon ? "fill" : isLine ? "line" : "circle";
  map.addLayer({
    id: layer.id,
    type: visual,
    source: layer.id,
    paint: layer.paint ?? {},
  } as Parameters<MlMap["addLayer"]>[0]);

  // For polygons, also add an outline line layer for a touch more definition.
  if (isPolygon && (layer.paint as Record<string, unknown>)?.["line-color"]) {
    const outlineId = `${layer.id}-outline`;
    if (!map.getLayer(outlineId)) {
      map.addLayer({
        id: outlineId,
        type: "line",
        source: layer.id,
        paint: {
          "line-color": (layer.paint as Record<string, unknown>)["line-color"],
          "line-width": (layer.paint as Record<string, unknown>)["line-width"] ?? 1,
          "line-opacity": (layer.paint as Record<string, unknown>)["line-opacity"] ?? 1,
        },
      } as Parameters<MlMap["addLayer"]>[0]);
      known.add(outlineId);
    }
  }
  known.add(layer.id);
}


function applyVisibility(map: MlMap, layers: StoryLayer[], visibility: Record<string, boolean>) {
  for (const layer of layers) {
    const visible = visibility[layer.id] !== false;
    const value = visible ? "visible" : "none";
    for (const id of [layer.id, `${layer.id}-outline`]) {
      if (map.getLayer(id)) {
        try {
          map.setLayoutProperty(id, "visibility", value);
        } catch {
          /* ignore */
        }
      }
    }
  }
}


function removeLayer(map: MlMap, id: string, known: Set<string>) {
  const outlineId = `${id}-outline`;
  if (map.getLayer(outlineId)) map.removeLayer(outlineId);
  if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(id)) map.removeSource(id);
  known.delete(id);
  known.delete(outlineId);
}


function fitToLayers(map: MlMap, layers: StoryLayer[]) {
  let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
  let touched = false;
  for (const layer of layers) {
    if (layer.kind !== "geojson" || !layer.data) continue;
    for (const f of (layer.data as GeoJSON.FeatureCollection).features ?? []) {
      forEachCoord(f.geometry, (lng, lat) => {
        if (lng < minLng) minLng = lng;
        if (lat < minLat) minLat = lat;
        if (lng > maxLng) maxLng = lng;
        if (lat > maxLat) maxLat = lat;
        touched = true;
      });
    }
  }
  if (!touched) return;
  if (minLng === maxLng && minLat === maxLat) {
    map.easeTo({ center: [minLng, minLat], zoom: 14, duration: 600 });
    return;
  }
  map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 60, maxZoom: 14, duration: 600 });
}


function forEachCoord(geom: GeoJSON.Geometry, fn: (lng: number, lat: number) => void) {
  const visit = (c: GeoJSON.Position | GeoJSON.Position[] | GeoJSON.Position[][] | GeoJSON.Position[][][]): void => {
    if (typeof c[0] === "number") {
      const pos = c as GeoJSON.Position;
      fn(pos[0], pos[1]);
      return;
    }
    (c as GeoJSON.Position[]).forEach(visit as never);
  };
  switch (geom.type) {
    case "Point": fn(geom.coordinates[0], geom.coordinates[1]); break;
    case "MultiPoint":
    case "LineString": geom.coordinates.forEach(([lng, lat]) => fn(lng, lat)); break;
    case "MultiLineString":
    case "Polygon": geom.coordinates.forEach((ring) => ring.forEach(([lng, lat]) => fn(lng, lat))); break;
    case "MultiPolygon": geom.coordinates.forEach((poly) => poly.forEach((ring) => ring.forEach(([lng, lat]) => fn(lng, lat)))); break;
    case "GeometryCollection": geom.geometries.forEach((g) => forEachCoord(g, fn)); break;
  }
}
