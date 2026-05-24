import type { StorymapResult } from "./storymap";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface UploadResponse {
  id: string;
  source_filename: string;
  locations: Array<{ id: string; name: string; lat: number | null; lng: number | null }>;
}

export async function uploadCsv(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch(`${API_BASE}/upload`, { method: "POST", body: form });
  if (!r.ok) throw new Error(`upload failed: ${r.status} ${await r.text()}`);
  return r.json();
}

export async function fetchStorymap(id: string): Promise<StorymapResult> {
  const r = await fetch(`${API_BASE}/storymap/${id}`);
  if (!r.ok) throw new Error(`storymap fetch failed: ${r.status}`);
  return r.json();
}

export interface ChatResponse {
  answer: string;
  sql: string | null;
  rows: Record<string, unknown>[];
  columns: string[];
  error: string | null;
  provider: string | null;
  history: { role: string; content: string }[];
}

export async function chatAsk(storymapId: string, message: string): Promise<ChatResponse> {
  const r = await fetch(`${API_BASE}/chat/${storymapId}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!r.ok) throw new Error(`chat failed: ${r.status} ${await r.text()}`);
  return r.json();
}

interface AnalyzeBody {
  network_id: string;
  user_intent?: string;
  clarification_answer?: string;
  archetypes?: ("diagnose" | "expand" | "rationalise")[];
}

interface AgentEvent {
  kind: string;
  payload: Record<string, unknown>;
}

/**
 * Parse a Server-Sent Events response from POST /analyze and invoke `onEvent`
 * for each event. The browser's EventSource doesn't support POST, so we use
 * fetch + a streaming reader.
 */
export async function analyzeStream(
  body: AnalyzeBody,
  onEvent: (ev: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok || !r.body) {
    throw new Error(`analyze failed: ${r.status}`);
  }
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  // The SSE spec terminates events with a blank line, which can be CRLF or LF
  // on the wire. sse-starlette emits CRLF — `indexOf("\n\n")` won't find that
  // because CR LF CR LF never contains two consecutive LFs. Match either.
  const SEP_RE = /\r?\n\r?\n/;
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let m: RegExpExecArray | null;
    while ((m = SEP_RE.exec(buffer)) !== null) {
      const chunk = buffer.slice(0, m.index);
      buffer = buffer.slice(m.index + m[0].length);
      const ev = parseSseChunk(chunk);
      if (ev) onEvent(ev);
    }
  }
  // Final flush — if the last event lacks a trailing blank line.
  if (buffer.trim()) {
    const ev = parseSseChunk(buffer);
    if (ev) onEvent(ev);
  }
}

function parseSseChunk(chunk: string): AgentEvent | null {
  let kind = "message";
  let dataLine = "";
  // Handle either CRLF or LF line endings within an event block.
  for (const line of chunk.split(/\r?\n/)) {
    if (line.startsWith("event:")) kind = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLine += line.slice(5).trim();
  }
  if (!dataLine) return null;
  try {
    return { kind, payload: JSON.parse(dataLine) as Record<string, unknown> };
  } catch {
    return { kind, payload: { raw: dataLine } };
  }
}
