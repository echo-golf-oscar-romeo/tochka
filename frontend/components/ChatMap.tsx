"use client";

/**
 * Small MapLibre map embedded inside the chat panel.
 *
 * Renders the geo-bearing rows from the most recent chat answer as points.
 * Auto-fits bounds to the result so the user sees the answer spatially.
 * Falls back to a blank paper-coloured canvas if the CSDI vector style URL
 * fails to load — the points still render on top.
 */

import { useEffect, useRef } from "react";
import maplibregl, { type Map as MlMap, type StyleSpecification } from "maplibre-gl";
import { csdiStyleUrl } from "@/lib/mapStyle";

export interface ChatPoint {
  id: string;
  lat: number;
  lng: number;
  label?: string;
  meta?: Record<string, unknown>;
}

const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#f6f4ef" } },
  ],
};

const POINTS_SOURCE = "chat-points";
const POINTS_LAYER = "chat-points-layer";
const POINTS_HALO  = "chat-points-halo";

export default function ChatMap({ points }: { points: ChatPoint[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MlMap | null>(null);
  const loadedRef = useRef(false);

  // ----- init once -----
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const initialStyle = (csdiStyleUrl() || FALLBACK_STYLE) as string | StyleSpecification;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: initialStyle,
      center: [114.165, 22.33],
      zoom: 10.5,
      attributionControl: { compact: true },
    });
    mapRef.current = map;

    // If the remote style fails, switch to the inline paper-colored canvas
    // so points still render and the dev overlay error is harmless.
    map.on("error", (e) => {
      // eslint-disable-next-line no-console
      console.warn("chat map style failed; falling back to blank canvas", e?.error);
      try {
        map.setStyle(FALLBACK_STYLE);
      } catch {
        /* ignore */
      }
    });

    const onLoad = () => {
      loadedRef.current = true;
      ensureLayer(map);
      applyPoints(map, points);
    };
    map.on("load", onLoad);
    // Re-add the source/layer if the style changes mid-flight.
    map.on("styledata", () => {
      if (loadedRef.current) {
        ensureLayer(map);
        applyPoints(map, points);
      }
    });

    return () => {
      loadedRef.current = false;
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ----- update points whenever they change -----
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (loadedRef.current) {
      applyPoints(map, points);
    }
  }, [points]);

  return <div ref={containerRef} className="w-full h-full" />;
}

function ensureLayer(map: MlMap) {
  if (!map.getSource(POINTS_SOURCE)) {
    map.addSource(POINTS_SOURCE, {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
  }
  if (!map.getLayer(POINTS_HALO)) {
    map.addLayer({
      id: POINTS_HALO,
      type: "circle",
      source: POINTS_SOURCE,
      paint: {
        "circle-radius": 14,
        "circle-color": "#0f5ea8",
        "circle-opacity": 0.18,
      },
    });
  }
  if (!map.getLayer(POINTS_LAYER)) {
    map.addLayer({
      id: POINTS_LAYER,
      type: "circle",
      source: POINTS_SOURCE,
      paint: {
        "circle-radius": 6,
        "circle-color": "#0f5ea8",
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 1.5,
      },
    });
  }
}

function applyPoints(map: MlMap, points: ChatPoint[]) {
  ensureLayer(map);
  const src = map.getSource(POINTS_SOURCE) as maplibregl.GeoJSONSource | undefined;
  if (!src) return;
  const fc: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: points.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lng, p.lat] },
      properties: { id: p.id, label: p.label ?? "" },
    })),
  };
  src.setData(fc);

  if (points.length > 0) {
    const lngs = points.map((p) => p.lng);
    const lats = points.map((p) => p.lat);
    const sw: [number, number] = [Math.min(...lngs), Math.min(...lats)];
    const ne: [number, number] = [Math.max(...lngs), Math.max(...lats)];
    if (points.length === 1) {
      map.flyTo({ center: [points[0].lng, points[0].lat], zoom: 14, duration: 600 });
    } else {
      map.fitBounds([sw, ne], { padding: 36, maxZoom: 15, duration: 700 });
    }
  }
}
