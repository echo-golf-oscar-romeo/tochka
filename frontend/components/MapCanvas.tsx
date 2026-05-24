"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import maplibregl, { type Map as MlMap, type StyleSpecification } from "maplibre-gl";
import { csdiStyleUrl } from "@/lib/mapStyle";
import type { Layer as StoryLayer } from "@/lib/storymap";

export interface MapCanvasHandle {
  map: () => MlMap | null;
}

interface Props {
  layers: StoryLayer[];
  initialCenter?: [number, number];
  initialZoom?: number;
  styleUrl?: string;
}

const MapCanvas = forwardRef<MapCanvasHandle, Props>(function MapCanvas(
  { layers, initialCenter = [114.165, 22.33], initialZoom = 11, styleUrl },
  ref,
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MlMap | null>(null);

  useImperativeHandle(ref, () => ({ map: () => mapRef.current }), []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: (styleUrl ?? csdiStyleUrl()) as unknown as StyleSpecification | string,
      center: initialCenter,
      zoom: initialZoom,
      attributionControl: { compact: true },
    });
    mapRef.current = map;

    map.on("load", () => {
      for (const layer of layers) {
        addLayer(map, layer);
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={containerRef} className="w-full h-full" />;
});

export default MapCanvas;

function addLayer(map: MlMap, layer: StoryLayer) {
  if (map.getSource(layer.id)) return;
  if (layer.kind === "geojson" && layer.data) {
    map.addSource(layer.id, { type: "geojson", data: layer.data as GeoJSON.FeatureCollection });
    const sample = (layer.data.features ?? [])[0]?.geometry?.type ?? "Point";
    const isPolygon = sample === "Polygon" || sample === "MultiPolygon";
    const isLine = sample === "LineString" || sample === "MultiLineString";
    const visual: "fill" | "line" | "circle" = isPolygon ? "fill" : isLine ? "line" : "circle";
    // The paint object shape varies by layer type; MapLibre's union of
    // FillLayerSpecification | LineLayerSpecification | CircleLayerSpecification
    // can't be narrowed from our generic StoryLayer at compile time, so we
    // cast to satisfy the union. Wrong paint keys for the chosen type will
    // simply be ignored at runtime.
    map.addLayer({
      id: layer.id,
      type: visual,
      source: layer.id,
      paint: layer.paint ?? {},
    } as Parameters<MlMap["addLayer"]>[0]);
  }
  // raster/vector/hex left for follow-up wiring.
}
