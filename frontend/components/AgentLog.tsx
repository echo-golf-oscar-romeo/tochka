"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { analyzeStream } from "@/lib/api";
import type { Archetype } from "./ArchetypePicker";
import ProgressTracker from "./ProgressTracker";

type Event = { kind: string; payload: Record<string, unknown> };

export default function AgentLog({ archetypes }: { archetypes?: Archetype[] }) {
  const params = useSearchParams();
  const router = useRouter();
  const networkId = params.get("network");
  const [events, setEvents] = useState<Event[]>([]);
  const [clarify, setClarify] = useState<{ question: string; options: string[] } | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!networkId) return;
    const abort = new AbortController();
    analyzeStream(
      {
        network_id: networkId,
        clarification_answer: answer ?? undefined,
        archetypes: archetypes,
      },
      (ev) => {
        if (abort.signal.aborted) return;
        setEvents((es) => [...es, ev]);
        if (ev.kind === "clarify") {
          setClarify({
            question: ev.payload.question as string,
            options: (ev.payload.options as string[]) ?? [],
          });
        }
        if (ev.kind === "storymap_ready") {
          const sid = ev.payload.storymap_id as string;
          setDone(true);
          setTimeout(() => router.push(`/story/${sid}`), 600);
        }
      },
      abort.signal,
    ).catch((err) => {
      // Cleanup-triggered aborts are expected; React 19 strict mode double-
      // invokes effects in dev, which cancels the first stream mid-read.
      if (err?.name === "AbortError") return;
      console.error("analyze stream failed:", err);
    });
    return () => abort.abort();
    // archetypes is stable per AgentLog mount (parent re-mounts when it changes).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [networkId, answer, router]);

  if (!networkId) return <p className="text-warn">No network id in URL.</p>;

  const hasError = events.some((ev) => ev.kind === "error");

  return (
    <div>
      <ProgressTracker events={events} hasError={hasError} />
      <details className="mb-3">
        <summary className="cursor-pointer text-xs uppercase tracking-wider text-muted mb-2">
          Event log ({events.length})
        </summary>
        <div className="space-y-2 font-mono text-xs mt-2">
          {events.map((ev, i) => {
            const isError = ev.kind === "error";
            return (
              <div key={i} className={`flex gap-3 ${isError ? "p-3 bg-warn/10 border border-warn/40 rounded" : ""}`}>
                <span className={`shrink-0 w-32 ${isError ? "text-warn font-bold" : "text-muted"}`}>
                  {ev.kind}
                </span>
                <span className={isError ? "text-warn" : "text-ink"}>{summarise(ev)}</span>
              </div>
            );
          })}
        </div>
      </details>

      {clarify && !answer && (
        <div className="mt-8 p-6 bg-paper border rounded">
          <p className="font-serif text-xl mb-4">{clarify.question}</p>
          <div className="flex gap-3">
            {clarify.options.map((opt) => (
              <button
                key={opt}
                className="rounded bg-accent text-white px-4 py-2"
                onClick={() => {
                  setEvents([]);
                  setClarify(null);
                  setAnswer(opt);
                }}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      )}
      {done && <p className="mt-6 text-good">Storymap ready — redirecting…</p>}
    </div>
  );
}

function summarise(ev: Event): string {
  const p = ev.payload as Record<string, unknown>;
  if (ev.kind === "thought") return String(p.text ?? "");
  if (ev.kind === "tool_call") return `→ ${p.tool}(${JSON.stringify(omit(p, "tool"))})`;
  if (ev.kind === "tool_result") return `← ${p.tool}: ${JSON.stringify(omit(p, "tool"))}`;
  if (ev.kind === "plan") return `plan: ${JSON.stringify(p.plan)}`;
  if (ev.kind === "clarify") return String(p.question);
  if (ev.kind === "narrating") {
    const prov = p.provider ? ` (${String(p.provider)})` : "";
    return `writing "${String(p.title ?? p.section_id)}"…${prov}`;
  }
  if (ev.kind === "storymap_ready") return `storymap ${p.storymap_id}`;
  if (ev.kind === "done") return "done";
  if (ev.kind === "error") return `${p.type ?? "Error"}: ${p.message ?? "(no message)"}`;
  return JSON.stringify(p);
}

function omit<T extends Record<string, unknown>>(obj: T, key: keyof T): Record<string, unknown> {
  const { [key]: _drop, ...rest } = obj;
  return rest;
}
