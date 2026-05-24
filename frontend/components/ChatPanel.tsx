"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { chatAsk, type ChatResponse } from "@/lib/api";
import ChatMap, { type ChatPoint } from "./ChatMap";

interface Message {
  role: "user" | "assistant";
  content: string;
  sql?: string | null;
  rows?: Record<string, unknown>[];
  columns?: string[];
  provider?: string | null;
  error?: string | null;
}

interface Props {
  storymapId: string;
  /** Per-network suggestions, computed by the workspace. */
  suggestions?: string[];
}

const DEFAULT_SUGGESTIONS = [
  "Which branches have the most banks within 500m?",
  "Are any of my branches within 500m of each other?",
  "Show competitor brands by district.",
];

export default function ChatPanel({ storymapId, suggestions }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, busy]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setBusy(true);
    try {
      const r: ChatResponse = await chatAsk(storymapId, trimmed);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: r.answer,
          sql: r.sql,
          rows: r.rows,
          columns: r.columns,
          provider: r.provider,
          error: r.error,
        },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: `Network error: ${String(e)}`, error: "network" },
      ]);
    } finally {
      setBusy(false);
    }
  }

  // Latest assistant answer with geo rows → drives the inline chat map.
  const mapPoints = useMemo<ChatPoint[]>(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role !== "assistant" || !m.rows || m.rows.length === 0) continue;
      const pts = extractPoints(m.rows);
      if (pts.length > 0) return pts;
    }
    return [];
  }, [messages]);

  const sug = suggestions && suggestions.length > 0 ? suggestions : DEFAULT_SUGGESTIONS;

  return (
    <div className="flex flex-col h-full">
      {mapPoints.length > 0 && (
        <div className="shrink-0 border-b border-border">
          <div className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wider text-muted">
            {mapPoints.length} on the map
          </div>
          <div className="h-52 w-full">
            <ChatMap points={mapPoints} />
          </div>
        </div>
      )}

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3 text-sm">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-muted text-xs leading-relaxed">
              The agent writes a read-only SELECT against your network + the HK competitor table, runs it, and explains the result.
            </p>
            <div className="space-y-1.5">
              {sug.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="block w-full text-left rounded border border-border hover:border-accent-400 hover:bg-accent-50 px-3 py-2 text-xs text-ink"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} m={m} />
        ))}
        {busy && (
          <div className="text-muted italic flex items-center gap-2 text-xs">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-500 animate-pulse" />
            writing SQL, executing, narrating…
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="shrink-0 border-t border-border p-2 flex gap-2"
      >
        <input
          type="text"
          placeholder="Ask about your network…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
          className="flex-1 rounded border border-border focus:border-accent-500 focus:ring-1 focus:ring-accent-100 outline-none px-3 py-1.5 text-sm disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded bg-accent-500 text-white px-3 py-1.5 text-sm hover:bg-accent-600 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </form>
    </div>
  );
}

function MessageBubble({ m }: { m: Message }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="rounded-lg bg-accent-500 text-white px-3 py-2 max-w-[85%] text-sm">{m.content}</div>
      </div>
    );
  }
  return (
    <div>
      <div
        className={`rounded-lg px-3 py-2 max-w-[97%] text-sm ${
          m.error ? "bg-accent-50 border border-accent-200 text-accent-900" : "bg-surface border border-border text-ink"
        }`}
      >
        <p className="whitespace-pre-wrap">{m.content}</p>
        {m.provider && (
          <p className="mt-1 text-[10px] text-subtle">via {m.provider}</p>
        )}
      </div>
      {m.sql && (
        <details className="mt-1 text-xs">
          <summary className="cursor-pointer text-muted">SQL ({(m.rows ?? []).length} rows)</summary>
          <pre className="mt-1 p-2 bg-surface border border-border rounded overflow-x-auto font-mono whitespace-pre text-[11px]">
            {m.sql}
          </pre>
          {m.rows && m.rows.length > 0 && (
            <div className="mt-2 overflow-x-auto">
              <table className="text-[11px] border-collapse w-full">
                <thead>
                  <tr className="text-left">
                    {(m.columns ?? Object.keys(m.rows[0])).map((c) => (
                      <th key={c} className="border-b border-border px-2 py-1 text-muted font-medium">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {m.rows.slice(0, 25).map((row, i) => (
                    <tr key={i} className="border-b border-rule">
                      {(m.columns ?? Object.keys(m.rows![0])).map((c) => (
                        <td key={c} className="px-2 py-1">
                          {formatCell(row[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {m.rows.length > 25 && (
                <p className="text-[10px] text-muted mt-1">+ {m.rows.length - 25} more rows…</p>
              )}
            </div>
          )}
        </details>
      )}
    </div>
  );
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  return String(v);
}

const LAT_KEYS = ["lat", "latitude", "y", "Lat", "Latitude"];
const LNG_KEYS = ["lng", "lon", "long", "longitude", "x", "Lng", "Lon", "Longitude"];

function pickNumber(row: Record<string, unknown>, keys: readonly string[]): number | null {
  for (const k of keys) {
    if (k in row) {
      const v = row[k];
      const n = typeof v === "number" ? v : parseFloat(String(v));
      if (Number.isFinite(n)) return n;
    }
  }
  return null;
}

function extractPoints(rows: Record<string, unknown>[]): ChatPoint[] {
  const out: ChatPoint[] = [];
  rows.forEach((row, i) => {
    const lat = pickNumber(row, LAT_KEYS);
    const lng = pickNumber(row, LNG_KEYS);
    if (lat === null || lng === null) return;
    if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return;
    const id = String(row.id ?? row.location_id ?? row.user_location_id ?? `r${i}`);
    const label = String(row.name ?? row.brand ?? row.title ?? "");
    out.push({ id, lat, lng, label, meta: row });
  });
  return out;
}
