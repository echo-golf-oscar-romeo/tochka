"use client";

/**
 * Scroll-driven storymap — ported from the Mapbox Storytelling template
 * (github.com/mapbox/storytelling) to MapLibre GL + React.
 *
 * Layout: sticky full-height map on the left, scrolling column of chapters on
 * the right. As the user scrolls, scrollama detects the active chapter, the
 * map flies to that chapter's location, and per-layer opacities update from
 * the chapter's `on_enter` / `on_exit` instructions.
 */

import { useEffect, useRef, useState } from "react";
import scrollama from "scrollama";
import type { Map as MlMap } from "maplibre-gl";
import MapCanvas, { type MapCanvasHandle } from "./MapCanvas";
import NetworkAtGlance from "./sections/NetworkAtGlance";
import WhoYouReach from "./sections/WhoYouReach";
import WhatsWorking from "./sections/WhatsWorking";
import Opportunity from "./sections/Opportunity";
import NextSteps from "./sections/NextSteps";
import type { StorymapResult, StorymapSection } from "@/lib/storymap";

interface SectionProps { section: StorymapSection; onFitToSection?: () => void }
const SECTION_COMPONENTS: Record<string, React.ComponentType<SectionProps>> = {
  "network-glance": NetworkAtGlance,
  "who-you-reach": WhoYouReach,
  "whats-working": WhatsWorking,
  "opportunity": Opportunity,
  "next-steps": NextSteps,
};

export default function Storymap({ data }: { data: StorymapResult }) {
  const mapHandle = useRef<MapCanvasHandle | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);

  useEffect(() => {
    const scroller = scrollama();
    scroller
      .setup({ step: ".storymap-chapter", offset: 0.5, progress: false })
      .onStepEnter((res) => {
        const idx = Number((res.element as HTMLElement).dataset.idx ?? 0);
        setActiveIdx(idx);
        const section = data.sections[idx];
        const map = mapHandle.current?.map();
        if (!section || !map) return;
        applyChapter(map, section);
      });
    const onResize = () => scroller.resize();
    window.addEventListener("resize", onResize);
    return () => {
      scroller.destroy();
      window.removeEventListener("resize", onResize);
    };
  }, [data.sections]);

  const initial = data.sections[0]?.location.center ?? [114.165, 22.33];

  return (
    <div className="storymap-shell">
      <div className="storymap-map">
        <MapCanvas
          ref={mapHandle}
          layers={data.layers}
          styleUrl={data.style_url}
          initialCenter={initial as [number, number]}
          initialZoom={data.sections[0]?.location.zoom ?? 11}
        />
      </div>
      <div className="bg-canvas">
        <header className="px-8 pt-16 pb-10 border-b border-border">
          <div className="flex items-center gap-2.5 mb-6">
            <span aria-hidden className="inline-block h-2 w-2 rounded-full accent-gradient" />
            <span className="text-[11px] uppercase tracking-wider text-muted">tochka · storymap</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-semibold tracking-tightish text-ink mb-3 leading-[1.1]">
            {data.summary?.split(".")[0] ?? "Your network"}
          </h1>
          <p className="text-[15px] text-ink/75 max-w-prose leading-relaxed">{data.summary}</p>
        </header>
        {data.sections.map((section, idx) => {
          const Comp = SECTION_COMPONENTS[section.id] ?? NetworkAtGlance;
          return (
            <section
              key={section.id}
              className="storymap-chapter"
              data-idx={idx}
              data-active={activeIdx === idx}
            >
              <Comp
                section={section}
                onFitToSection={() => {
                  const map = mapHandle.current?.map();
                  if (map) applyChapter(map, section);
                }}
              />
            </section>
          );
        })}
        <footer className="px-8 py-12 text-sm text-muted">
          Powered by Qwen · grounded in CSDI · tochka
        </footer>
      </div>
    </div>
  );
}

function applyChapter(map: MlMap, section: StorymapSection) {
  map.flyTo({
    center: section.location.center as [number, number],
    zoom: section.location.zoom,
    pitch: section.location.pitch ?? 0,
    bearing: section.location.bearing ?? 0,
    duration: 1800,
    essential: true,
  });
  for (const op of section.on_enter ?? []) {
    if (map.getLayer(op.layer)) {
      const type = (map.getLayer(op.layer) as { type: string }).type;
      const propByType: Record<string, string> = {
        fill: "fill-opacity",
        line: "line-opacity",
        circle: "circle-opacity",
        symbol: "icon-opacity",
        raster: "raster-opacity",
      };
      const prop = propByType[type] ?? "fill-opacity";
      try {
        map.setPaintProperty(op.layer, prop, op.opacity);
      } catch {
        /* ignore — paint property not applicable to this layer type */
      }
    }
  }
}
