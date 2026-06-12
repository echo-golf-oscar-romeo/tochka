"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import maplibregl, { type Map as MlMap, type StyleSpecification } from "maplibre-gl";
import { csdiStyleUrl, makeMapboxTransformRequest, mapboxToken } from "@/lib/mapStyle";
import type { Layer as StoryLayer } from "@/lib/storymap";

export interface MapCanvasHandle {
  map: () => MlMap | null;
  screenshot: () => string | null;
  applyPaintUpdates: (updates: { layer_id: string; paint: Record<string, unknown> }[]) => void;
}

interface Props {
  layers: StoryLayer[];
  initialCenter?: [number, number];
  initialZoom?: number;
  styleUrl?: string;
  autoFit?: boolean;
  visibility?: Record<string, boolean>;
  /** false → static thumbnail (no pan/zoom/controls), used inside reports. */
  interactive?: boolean;
}

const MapCanvas = forwardRef<MapCanvasHandle, Props>(function MapCanvas(
  { layers, initialCenter = [114.165, 22.33], initialZoom = 11, styleUrl, autoFit = true,
    visibility, interactive = true },
  ref,
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MlMap | null>(null);
  const loadedRef = useRef(false);
  const knownLayersRef = useRef<Set<string>>(new Set());
  const layersRef = useRef<StoryLayer[]>(layers);
  layersRef.current = layers;
  const popupRef = useRef<maplibregl.Popup | null>(null);

  useImperativeHandle(ref, () => ({
    map: () => mapRef.current,
    screenshot: () => {
      const m = mapRef.current;
      if (!m) return null;
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

    // When the basemap comes from Mapbox, the fetched style JSON embeds
    // `mapbox://` URIs for vector sources, sprites, and glyphs. MapLibre
    // can't resolve those natively — without a transformRequest hook the
    // map renders as a blank white canvas. mapboxToken() returns null when
    // no token is set, in which case we pass `undefined` and MapLibre
    // handles non-Mapbox styles (like Carto Positron) directly.
    const token = mapboxToken();
    const transformRequest = makeMapboxTransformRequest(token);
    const resolvedStyleUrl = styleUrl ?? csdiStyleUrl();
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console
      console.info(
        "[MapCanvas] init style=%s tokenInBundle=%s",
        resolvedStyleUrl,
        token ? `pk…${token.slice(-6)}` : "(none)",
      );
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: resolvedStyleUrl as unknown as StyleSpecification | string,
      center: initialCenter,
      zoom: initialZoom,
      attributionControl: { compact: true },
      preserveDrawingBuffer: true, // needed for screenshot capture
      transformRequest,
      interactive,
      // MapLibre's style validator is stricter than the Mapbox style spec.
      // Mapbox styles include extensions (e.g. nested `name` fields inside
      // imports/iconsets) that MapLibre flags as "unknown property", and a
      // SINGLE validation error makes Style._load() return early — sources,
      // sprites, and glyphs never fetch, the map renders blank, and the
      // transformRequest hook is never called. Disabling validation here
      // lets MapLibre load Mapbox styles end-to-end. Our chosen styles
      // (Mapbox or Carto Positron) are both known-good; we don't lose
      // anything safety-wise.
      validateStyle: false,
    });
    mapRef.current = map;

    // Built-in MapLibre controls — skipped for static report thumbnails.
    if (interactive) {
      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true, showCompass: true }), "top-right");
      map.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 110 }), "bottom-right");
    }

    // Errors are logged only — we never auto-swap the style anymore. The
    // earlier auto-swap to FALLBACK_STYLE fired on transient tile 404s and
    // nuked the basemap mid-session. With Carto Positron as the default
    // (which doesn't 404), this isn't needed.
    map.on("error", (e) => {
      const err = e?.error as (Error & { url?: string; status?: number }) | undefined;
      // eslint-disable-next-line no-console
      console.warn(
        "[MapLibre] %s%s%s",
        err?.message ?? String(e),
        err?.status ? ` [HTTP ${err.status}]` : "",
        err?.url ? ` ← ${err.url}` : "",
      );
    });

    map.on("load", () => {
      loadedRef.current = true;
      knownLayersRef.current.clear();
      for (const layer of layersRef.current) {
        try {
          addOrReplaceLayer(map, layer, knownLayersRef.current);
        } catch (err) {
          console.warn("addOrReplaceLayer failed for", layer.id, err);
        }
      }
      if (autoFit) fitToLayers(map, layersRef.current);
    });

    // Single delegated click handler so any added point layer (user network,
    // chat-N, future custom layers) gets a popup with its feature properties.
    map.on("click", (e) => {
      const point = e.point;
      const allPointLayers = knownLayersRef.current
        ? Array.from(knownLayersRef.current).filter((id) => {
            try {
              return map.getLayer(id) && (map.getLayer(id) as { type: string }).type === "circle";
            } catch { return false; }
          })
        : [];
      if (allPointLayers.length === 0) return;
      const features = map.queryRenderedFeatures(point, { layers: allPointLayers });
      if (!features.length) return;
      const f = features[0];
      const props = (f.properties ?? {}) as Record<string, unknown>;
      const html = renderPopupHtml(props);
      if (!html) return;
      if (f.geometry.type !== "Point") return;
      const coords = f.geometry.coordinates as [number, number];
      if (popupRef.current) popupRef.current.remove();
      popupRef.current = new maplibregl.Popup({ closeButton: true, offset: 10, className: "tochka-popup" })
        .setLngLat(coords)
        .setHTML(html)
        .addTo(map);
    });
    // Pointer cursor on point hover for affordance.
    map.on("mousemove", (e) => {
      const allPointLayers = Array.from(knownLayersRef.current).filter((id) => {
        try { return map.getLayer(id) && (map.getLayer(id) as { type: string }).type === "circle"; }
        catch { return false; }
      });
      if (!allPointLayers.length) return;
      const hits = map.queryRenderedFeatures(e.point, { layers: allPointLayers });
      map.getCanvas().style.cursor = hits.length ? "pointer" : "";
    });

    return () => {
      loadedRef.current = false;
      if (popupRef.current) { popupRef.current.remove(); popupRef.current = null; }
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
      try {
        addOrReplaceLayer(map, layer, knownLayersRef.current);
      } catch (err) {
        console.warn("addOrReplaceLayer failed for", layer.id, err);
      }
    }
    for (const known of Array.from(knownLayersRef.current)) {
      if (!incoming.has(known) && !known.endsWith("-outline")) {
        try {
          removeLayer(map, known, knownLayersRef.current);
        } catch (err) {
          console.warn("removeLayer failed for", known, err);
        }
      }
    }
    applyVisibility(map, layers, visibility ?? {});
    applyOrder(map, layers);
    if (autoFit) fitToLayers(map, layers);
  }, [layers, autoFit, visibility]);

  return <div ref={containerRef} className="w-full h-full" />;
});

export default MapCanvas;


function renderPopupHtml(props: Record<string, unknown>): string | null {
  const name = props.name ?? props.brand ?? props.id;
  if (!name) return null;
  const rows: string[] = [];
  rows.push(`<div class="text-sm font-semibold text-ink">${escapeHtml(String(name))}</div>`);
  for (const key of ["brand", "type", "district", "capacity", "actual_volume", "distance_m", "score"]) {
    const v = props[key];
    if (v === null || v === undefined || v === "") continue;
    rows.push(`<div class="text-[11px] text-muted"><span class="text-ink/70">${key}:</span> ${escapeHtml(String(v))}</div>`);
  }
  return `<div class="space-y-0.5">${rows.join("")}</div>`;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c] ?? c));
}


function addOrReplaceLayer(map: MlMap, layer: StoryLayer, known: Set<string>) {
  if (layer.kind !== "geojson" || !layer.data) return;
  const data = layer.data as GeoJSON.FeatureCollection;
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
  // CRITICAL: a MapLibre layer only accepts paint props of ITS type. Our
  // layer specs mix fill-* and line-* (fill + outline in one spec) — passing
  // line-color into a `fill` layer makes addLayer THROW, the catch upstream
  // swallows it, and the polygon silently never renders ("polygons have no
  // fill"). Filter to the prefix the layer type accepts; line-* goes to the
  // separate -outline layer below.
  const paintAll = (layer.paint ?? {}) as Record<string, unknown>;
  const paintFor = (prefix: string) =>
    Object.fromEntries(Object.entries(paintAll).filter(([k]) => k.startsWith(prefix)));
  map.addLayer({
    id: layer.id,
    type: visual,
    source: layer.id,
    paint: paintFor(`${visual}-`),
  } as Parameters<MlMap["addLayer"]>[0]);

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


/** Restack map layers so the array order in props matches the visual order:
 *  array index 0  → topmost on the map (top of the layers panel).
 *  MapLibre stacks later-added on top, so we walk the array in REVERSE
 *  and `moveLayer(id)` (no beforeId → move to top) each one. After the
 *  loop the first array entry is the most-recently-moved-to-top, i.e.
 *  topmost. Outline companion layers move with their parent. */
function applyOrder(map: MlMap, layers: StoryLayer[]) {
  for (let i = layers.length - 1; i >= 0; i--) {
    const id = layers[i].id;
    try {
      if (map.getLayer(id)) map.moveLayer(id);
      const outlineId = `${id}-outline`;
      if (map.getLayer(outlineId)) map.moveLayer(outlineId);
    } catch {
      /* ignore — layer might have just been removed */
    }
  }
}


function applyVisibility(map: MlMap, layers: StoryLayer[], visibility: Record<string, boolean>) {
  for (const layer of layers) {
    const visible = visibility[layer.id] !== false;
    const value = visible ? "visible" : "none";
    for (const id of [layer.id, `${layer.id}-outline`]) {
      if (map.getLayer(id)) {
        try { map.setLayoutProperty(id, "visibility", value); } catch { /* ignore */ }
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
        // Defensive: a feature with swapped/garbage coordinates must not be
        // allowed to poison the bounds and crash MapLibre's LngLat check.
        if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;
        if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return;
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
