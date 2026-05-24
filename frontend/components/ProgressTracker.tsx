"use client";

/**
 * Phase tracker for the agent run.
 *
 * Derives the current phase from the stream of agent events — no backend
 * changes required. Each phase has a list of event "kinds" or "tool" names
 * that match it; the latest match wins. Phases before that are done;
 * phases after are pending.
 */

import type { ReactNode } from "react";

export interface AgentEvent {
  kind: string;
  payload: Record<string, unknown>;
}

type Status = "pending" | "active" | "done";

interface Phase {
  id: string;
  label: string;
  hint: string;
  matchKinds?: string[];
  matchTools?: string[];
}

const PHASES: Phase[] = [
  { id: "inspect",     label: "Inspect network",                hint: "parsing + classifying POI type",                 matchKinds: ["thought"] },
  { id: "geocode",     label: "Geocode addresses",              hint: "via CSDI ALS",                                   matchTools: ["als_lookup"] },
  { id: "plan",        label: "Decide methodology + data plan", hint: "demand model + analytical archetype",            matchKinds: ["plan"] },
  { id: "isochrones",  label: "Walking catchments",             hint: "Mapbox isochrone polygons",                      matchTools: ["isochrone_walk"] },
  { id: "competitors", label: "Competitor banks + ATMs",        hint: "DuckDB-spatial scan over HK OSM POIs",           matchTools: ["competitors_in_radius"] },
  { id: "population",  label: "Catchment population",           hint: "people inside each isochrone",                   matchTools: ["population_in_polygon"] },
  { id: "score",       label: "Score locations",                hint: "Huff share via DuckDB SQL",                      matchTools: ["huff_model", "gravity_score"] },
  { id: "anomalies",   label: "Detect anomalies",               hint: "actual vs expected, ratio + stdev",              matchTools: ["anomaly_detect"] },
  { id: "compose",     label: "Compose storymap",               hint: "five sections + layers",                         matchTools: ["make_storymap_section"] },
  { id: "narrate",     label: "Write narrative",                hint: "LLM rewrites each section description",          matchKinds: ["narrating"] },
  { id: "ready",       label: "Ready",                          hint: "redirecting to storymap…",                       matchKinds: ["storymap_ready", "done"] },
];

function matchPhase(phase: Phase, ev: AgentEvent): boolean {
  if (phase.matchKinds?.includes(ev.kind)) return true;
  if (phase.matchTools && ev.payload?.tool && phase.matchTools.includes(String(ev.payload.tool))) return true;
  return false;
}

function computePhaseIdx(events: AgentEvent[]): number {
  let idx = -1;
  for (const ev of events) {
    for (let i = PHASES.length - 1; i >= 0; i--) {
      if (matchPhase(PHASES[i], ev)) {
        if (i > idx) idx = i;
        break;
      }
    }
  }
  return idx;
}

function statusFor(i: number, current: number, hasError: boolean): Status {
  if (i < current) return "done";
  if (i === current) return hasError ? "done" : "active";
  return "pending";
}

interface PlanRow { layer: string; source: string; status?: string; }

function findPlan(events: AgentEvent[]): PlanRow[] | null {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].kind === "plan") {
      const plan = events[i].payload?.plan;
      if (Array.isArray(plan)) return plan as PlanRow[];
    }
  }
  return null;
}

function narrationProgress(events: AgentEvent[]): { current: number; titles: string[] } {
  const titles: string[] = [];
  for (const ev of events) {
    if (ev.kind === "narrating") {
      const t = String(ev.payload?.title ?? ev.payload?.section_id ?? "");
      if (t) titles.push(t);
    }
  }
  return { current: titles.length, titles };
}

const TOTAL_SECTIONS = 5;

export default function ProgressTracker({
  events,
  hasError,
}: {
  events: AgentEvent[];
  hasError: boolean;
}) {
  const currentIdx = computePhaseIdx(events);
  const plan = findPlan(events);
  const narration = narrationProgress(events);

  return (
    <section className="mb-8 rounded-lg border border-muted/30 bg-white p-5">
      <h2 className="text-xs uppercase tracking-wider text-muted mb-4">Progress</h2>
      <ol className="space-y-1.5">
        {PHASES.map((p, i) => {
          const status = statusFor(i, currentIdx, hasError);
          const extra = renderExtra(p, status, narration, plan);
          return (
            <li key={p.id} className="flex items-start gap-3 text-sm">
              <StatusDot status={status} />
              <div className="flex-1">
                <div className={status === "pending" ? "text-muted" : "text-ink"}>
                  <span className={status === "active" ? "font-medium" : ""}>{p.label}</span>
                  <span className="text-muted"> · {p.hint}</span>
                </div>
                {extra}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function StatusDot({ status }: { status: Status }): ReactNode {
  if (status === "done") {
    return (
      <span className="mt-1 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-good text-white text-[10px] leading-none">
        ✓
      </span>
    );
  }
  if (status === "active") {
    return (
      <span className="mt-1 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-accent">
        <span className="h-2 w-2 rounded-full bg-white animate-pulse" />
      </span>
    );
  }
  return (
    <span className="mt-1 inline-block h-4 w-4 shrink-0 rounded-full border border-muted/40" />
  );
}

function renderExtra(
  phase: Phase,
  status: Status,
  narration: { current: number; titles: string[] },
  plan: PlanRow[] | null,
): ReactNode {
  if (phase.id === "plan" && status !== "pending" && plan) {
    return (
      <ul className="mt-1 ml-1 text-xs text-muted space-y-0.5">
        {plan.map((row, i) => (
          <li key={i}>
            <span className="text-ink/80">{row.layer}</span> · {row.source}
          </li>
        ))}
      </ul>
    );
  }
  if (phase.id === "narrate" && (status === "active" || status === "done")) {
    const last = narration.titles[narration.titles.length - 1];
    return (
      <div className="mt-1 text-xs text-muted">
        {narration.current} / {TOTAL_SECTIONS}
        {last ? <span className="text-ink/80"> — writing &ldquo;{last}&rdquo;…</span> : null}
      </div>
    );
  }
  return null;
}
