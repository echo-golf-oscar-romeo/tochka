"use client";

import { useEffect, useRef, useState } from "react";
import { chatAsk, type ChatResponse } from "@/lib/api";

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
  initialOpen?: boolean;
}

const SUGGESTIONS = [
  "Which branches have the most banks within 500m?",
  "Which BOC branches in my network are within 200m of an HSBC?",
  "List branches with capacity utilisation over 100%.",
  "Are any of my branches within 500m of each other? (cannibalisation)",
];

export default function ChatPanel({ storymapId, initialOpen = true }: Props) {
  const [open, setOpen] = useState(initialOpen);
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

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed right-4 bottom-4 z-30 rounded-full bg-accent text-white px-4 py-2 shadow-lg text-sm"
      >
        Ask the data
      </button>
    );
  }

  return (
    <aside className="fixed right-0 top-0 bottom-0 z-30 w-full sm:w-[28rem] bg-white border-l border-muted/30 flex flex-col shadow-xl">
      <header className="px-4 py-3 border-b border-muted/30 flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-accent font-semibold">Ask the data</div>
          <div className="text-xs text-muted">Spatial SQL via DuckDB · grounded in OSM HK</div>
        </div>
        <button
          type="button"
          aria-label="Close chat"
          onClick={() => setOpen(false)}
          className="text-muted hover:text-ink px-2"
        >
          ✕
        </button>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3 text-sm">
        {messages.length === 0 && (
          <div className="text-muted">
            <p className="mb-3">
              Ask follow-up questions about your network. The agent writes a SELECT query against your
              uploaded locations and the HK competitor POI table, runs it, and explains the answer.
            </p>
            <div className="space-y-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="block w-full text-left rounded border border-muted/30 hover:border-accent px-3 py-2 text-xs"
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
          <div className="text-muted italic flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
            writing SQL, executing, narrating…
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="border-t border-muted/30 p-3 flex gap-2"
      >
        <input
          type="text"
          placeholder="Ask about your network…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
          className="flex-1 rounded border border-muted/30 px-3 py-2 text-sm focus:outline-none focus:border-accent disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded bg-accent text-white px-4 py-2 text-sm disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </aside>
  );
}

function MessageBubble({ m }: { m: Message }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="rounded-lg bg-accent text-white px-3 py-2 max-w-[85%]">{m.content}</div>
      </div>
    );
  }
  return (
    <div>
      <div
        className={`rounded-lg px-3 py-2 max-w-[95%] ${
          m.error ? "bg-warn/10 border border-warn/40 text-warn" : "bg-paper border border-muted/20 text-ink"
        }`}
      >
        <p className="whitespace-pre-wrap">{m.content}</p>
        {m.provider && (
          <p className="mt-1 text-[10px] text-muted">via {m.provider}</p>
        )}
      </div>
      {m.sql && (
        <details className="mt-1 text-xs">
          <summary className="cursor-pointer text-muted">SQL ({(m.rows ?? []).length} rows)</summary>
          <pre className="mt-1 p-2 bg-paper border border-muted/20 rounded overflow-x-auto font-mono whitespace-pre">
            {m.sql}
          </pre>
          {m.rows && m.rows.length > 0 && (
            <div className="mt-2 overflow-x-auto">
              <table className="text-[11px] border-collapse w-full">
                <thead>
                  <tr className="text-left">
                    {(m.columns ?? Object.keys(m.rows[0])).map((c) => (
                      <th key={c} className="border-b border-muted/30 px-2 py-1 text-muted font-medium">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {m.rows.slice(0, 25).map((row, i) => (
                    <tr key={i} className="border-b border-muted/10">
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
