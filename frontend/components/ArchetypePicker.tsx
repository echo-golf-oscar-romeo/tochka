"use client";

import { useState } from "react";

export type Archetype = "diagnose" | "expand" | "rationalise";

const OPTIONS: { id: Archetype; title: string; lead: string; body: string }[] = [
  {
    id: "diagnose",
    title: "Diagnose",
    lead: "How is my current network performing?",
    body: "Anomaly detection against a Huff/gravity baseline — who's under-performing, who's beating expectations, and what the catchment data says about why.",
  },
  {
    id: "expand",
    title: "Expand",
    lead: "Where should I open next?",
    body: "Gap analysis on a hex grid: rank every 250 m cell in the city by uncovered demand, weighted by reachability and competition. Shortlist the top candidate locations with rationale.",
  },
  {
    id: "rationalise",
    title: "Rationalise",
    lead: "Which locations should I close, merge, or resize?",
    body: "Cannibalisation analysis between your own branches plus competitor overlap. Identify redundant coverage, mergeable pairs, and over-capacity sites.",
  },
];

export default function ArchetypePicker({
  onSubmit,
}: {
  onSubmit: (archetypes: Archetype[]) => void;
}) {
  const [selected, setSelected] = useState<Set<Archetype>>(new Set());

  function toggle(id: Archetype) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div>
      <p className="text-sm text-muted mb-6">
        Pick at least one. You can combine — the agent will sequence its tools accordingly.
      </p>

      <div className="grid gap-4 md:grid-cols-3 mb-8">
        {OPTIONS.map((opt) => {
          const isOn = selected.has(opt.id);
          return (
            <button
              type="button"
              key={opt.id}
              onClick={() => toggle(opt.id)}
              className={`text-left rounded-lg border p-5 transition ${
                isOn
                  ? "border-accent bg-accent/5 ring-2 ring-accent/30"
                  : "border-muted/30 hover:border-muted/60 bg-white"
              }`}
              aria-pressed={isOn}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-serif text-xl">{opt.title}</span>
                <span
                  className={`inline-block w-4 h-4 rounded border ${
                    isOn ? "bg-accent border-accent" : "border-muted/40 bg-white"
                  }`}
                  aria-hidden
                />
              </div>
              <p className="text-sm text-ink/90 mb-2">{opt.lead}</p>
              <p className="text-xs text-muted">{opt.body}</p>
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={selected.size === 0}
          onClick={() => onSubmit(Array.from(selected))}
          className="rounded bg-accent text-white px-5 py-2 text-sm disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Run analysis
        </button>
        {selected.size === 0 && (
          <span className="text-xs text-muted">Select at least one archetype.</span>
        )}
      </div>
    </div>
  );
}
