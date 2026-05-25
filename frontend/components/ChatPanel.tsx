"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { chatAsk, chatNetwork, type ChatResponse } from "@/lib/api";
import ChatMap, { type ChatPoint } from "./ChatMap";
import ChatChart from "./ChatChart";

interface Message {
  role: "user" | "assistant";
  content: string;
  sql?: string | null;
  rows?: Record<string, unknown>[];
  columns?: string[];
  provider?: string | null;
  error?: string | null;
  /** The user question that produced this assistant answer — used as the
   *  layer label when the answer auto-creates a map layer. */
  prompt?: string | null;
}

interface Props {
  /** If a storymap exists for the current network, prefer that endpoint
   *  so the chat sees the storymap's summary context. Else, chat against
   *  the network directly. */
  storymapId?: string | null;
  networkId?: string | null;
  /** Per-network suggestions, computed by the workspace. */
  suggestions?: string[];
  /** Names of layers currently on the map, used for "/" autocomplete. */
  layerNames?: string[];
  /** Optional callback — fires when the user clicks "Add to map" on a
   *  message with geo rows. The parent creates a layer on the main map. */
  onAddPointsToMap?: (label: string, points: ChatPoint[]) => void;
}

const DEFAULT_SUGGESTIONS = [
  "Which branches have the most banks within 500m?",
  "Are any of my branches within 500m of each other?",
  "Show competitor brands by district.",
];

export default function ChatPanel({
  storymapId, networkId, suggestions, layerNames, onAddPointsToMap,
}: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [slashOpen, setSlashOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  // Tracks which assistant-message indices have already been pushed to the
  // main map, so we only auto-add each answer once.
  const autoAddedRef = useRef<Set<number>>(new Set());

  const handleId = storymapId ?? networkId ?? null;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, busy]);

  // Reset history when the current handle changes (different upload).
  useEffect(() => {
    setMessages([]);
    setInput("");
    autoAddedRef.current.clear();
  }, [networkId]);

  // Auto-add: every assistant message with geo rows becomes a real map layer.
  // This is THE prompt-based-GIS interaction — chat drives the map.
  useEffect(() => {
    if (!onAddPointsToMap) return;
    messages.forEach((m, i) => {
      if (m.role !== "assistant" || !m.rows || m.rows.length === 0) return;
      if (autoAddedRef.current.has(i)) return;
      const pts = extractPoints(m.rows);
      if (pts.length === 0) return;
      autoAddedRef.current.add(i);
      const label = labelFromPrompt(m.prompt) || `chat #${i + 1}`;
      onAddPointsToMap(label, pts);
    });
  }, [messages, onAddPointsToMap]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy || !handleId) return;
    setInput("");
    setSlashOpen(false);
    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setBusy(true);
    try {
      const r: ChatResponse = storymapId
        ? await chatAsk(storymapId, trimmed)
        : await chatNetwork(networkId!, trimmed);
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
          prompt: trimmed,
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

  // Slash menu — current layer names as completions.
  const slashOptions = useMemo(() => {
    const head = input.split(/\s+/).pop() ?? "";
    if (!head.startsWith("/")) return [];
    const q = head.slice(1).toLowerCase();
    return (layerNames ?? []).filter((n) => n.toLowerCase().includes(q));
  }, [input, layerNames]);

  function pickSlash(option: string) {
    // Replace the in-progress /token with the chosen quoted layer name.
    const tokens = input.split(/\s+/);
    tokens[tokens.length - 1] = `"${option}"`;
    setInput(tokens.join(" ") + " ");
    setSlashOpen(false);
  }

  return (
    <div className="flex flex-col h-full bg-canvas">
      {mapPoints.length > 0 && (
        <div className="shrink-0 border-b border-border">
          <div className="px-3 pt-2 pb-1 flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider text-muted">
              {mapPoints.length} on the chat map
            </span>
            <span className="text-[10px] text-subtle">geo answer</span>
          </div>
          <div className="h-48 w-full">
            <ChatMap points={mapPoints} />
          </div>
        </div>
      )}

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3 text-sm">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-muted text-xs leading-relaxed">
              The agent writes a read-only spatial SELECT against your network + the HK competitor table, runs it, and explains the result. Type <code className="text-ink">/</code> to reference a layer.
            </p>
            <div className="space-y-1.5">
              {sug.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  disabled={!handleId || busy}
                  className="block w-full text-left rounded border border-border hover:border-accent-400 hover:bg-accent-50 px-3 py-2 text-xs text-ink disabled:opacity-50"
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
        className="shrink-0 border-t border-border p-2 relative"
      >
        {slashOpen && slashOptions.length > 0 && (
          <div className="absolute bottom-full left-2 right-2 mb-1 rounded border border-border bg-canvas shadow-pop max-h-44 overflow-y-auto">
            <div className="px-2 py-1.5 text-[10px] uppercase tracking-wider text-muted border-b border-border">
              Insert layer
            </div>
            <ul>
              {slashOptions.map((opt) => (
                <li key={opt}>
                  <button
                    type="button"
                    onClick={() => pickSlash(opt)}
                    className="w-full text-left px-3 py-1.5 text-sm hover:bg-accent-50 hover:text-accent-700"
                  >
                    {opt}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="flex gap-2">
          <input
            type="text"
            placeholder={handleId ? "Ask about your network…" : "Upload a network first"}
            value={input}
            onChange={(e) => {
              const v = e.target.value;
              setInput(v);
              const head = v.split(/\s+/).pop() ?? "";
              setSlashOpen(head.startsWith("/"));
            }}
            onFocus={() => {
              const head = input.split(/\s+/).pop() ?? "";
              if (head.startsWith("/")) setSlashOpen(true);
            }}
            onBlur={() => setTimeout(() => setSlashOpen(false), 150)}
            disabled={busy || !handleId}
            className="flex-1 rounded border border-border focus:border-accent-500 focus:ring-2 focus:ring-accent-100 outline-none px-3 py-1.5 text-sm disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={busy || !input.trim() || !handleId}
            className="rounded bg-ink hover:bg-accent-700 text-canvas px-3 py-1.5 text-sm disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}

interface MessageBubbleProps {
  m: Message;
}

function MessageBubble({ m }: MessageBubbleProps) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="rounded-lg bg-ink text-canvas px-3 py-2 max-w-[85%] text-sm shadow-card">{m.content}</div>
      </div>
    );
  }

  const geoPoints = m.rows ? extractPoints(m.rows) : [];
  const chartCols = m.columns ?? (m.rows && m.rows[0] ? Object.keys(m.rows[0]) : []);

  return (
    <div>
      <div
        className={`rounded-lg px-3 py-2 max-w-[97%] text-sm shadow-card ${
          m.error ? "bg-highlight-50 border border-highlight-100 text-ink" : "bg-surface border border-border text-ink"
        }`}
      >
        <p className="whitespace-pre-wrap">{m.content}</p>
        <div className="mt-1 flex items-center gap-2 text-[10px] text-subtle">
          {m.provider && <span>via {m.provider}</span>}
          {geoPoints.length > 0 && (
            <span className="text-accent-600">
              ↳ added {geoPoints.length} {geoPoints.length === 1 ? "point" : "points"} as a map layer
            </span>
          )}
        </div>
      </div>

      {/* Inline chart, when the row shape is chartable. */}
      {m.rows && m.rows.length >= 2 && (
        <ChatChart rows={m.rows} columns={chartCols} />
      )}

      {m.sql && (
        <details className="mt-1 text-xs">
          <summary className="cursor-pointer text-muted">SQL · {(m.rows ?? []).length} rows</summary>
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

/** Turn a user question into a short, legible layer label.
 *  "Which 10 competitor banks are closest to Central?" -> "10 competitor banks closest to Central"
 *  "Show all branches with their nearest competitor distance." -> "All branches with their nearest competitor distance" */
function labelFromPrompt(prompt: string | null | undefined): string {
  if (!prompt) return "";
  let s = prompt.trim().replace(/[?.!]+$/g, "");
  // Strip common question/command leaders.
  s = s.replace(
    /^(?:please\s+)?(?:can you|could you|would you|i want to|i'd like to|let's|let me|tell me|show me|show|find|list|get|display|plot|map|give me|fetch|return|highlight|which|what(?:'s| is| are)?|where(?:'s| is| are)?|how many|how much|are there|is there)\s+/i,
    "",
  );
  s = s.trim();
  // Sentence-case (capitalise first letter only) and truncate.
  if (s.length > 0) s = s[0].toUpperCase() + s.slice(1);
  if (s.length > 60) s = s.slice(0, 57).trimEnd() + "…";
  return s;
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
