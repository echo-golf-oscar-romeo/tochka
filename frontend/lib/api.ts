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
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep = buffer.indexOf("\n\n");
    while (sep !== -1) {
      const chunk = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const ev = parseSseChunk(chunk);
      if (ev) onEvent(ev);
      sep = buffer.indexOf("\n\n");
    }
  }
}

function parseSseChunk(chunk: string): AgentEvent | null {
  let kind = "message";
  let dataLine = "";
  for (const line of chunk.split("\n")) {
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
