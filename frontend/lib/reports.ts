// Saved-reports store — localStorage-backed so reports survive a reload
// without needing backend persistence. Each saved report embeds the full
// StorymapResult spec, so reopening is instant and offline-safe.

import type { StorymapResult } from "./storymap";

export interface SavedReport {
  id: string;
  title: string;
  summary: string;
  createdAt: string; // ISO
  spec: StorymapResult;
}

const KEY = "tochka.reports.v1";

function read(): SavedReport[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    const list = raw ? (JSON.parse(raw) as SavedReport[]) : [];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

function write(list: SavedReport[]) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    // Quota exceeded (specs embed layer GeoJSON) — drop the oldest and retry once.
    try {
      window.localStorage.setItem(KEY, JSON.stringify(list.slice(0, 5)));
    } catch {
      /* give up quietly */
    }
  }
}

export function listReports(): SavedReport[] {
  return read().sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export function saveReport(spec: StorymapResult, title?: string): SavedReport {
  const list = read().filter((r) => r.id !== spec.id);
  const item: SavedReport = {
    id: spec.id,
    title: title ?? (spec.summary?.split(".")[0] ?? "Network report"),
    summary: spec.summary ?? "",
    createdAt: new Date().toISOString(),
    spec,
  };
  // Most-recent first; cap at 12 to respect localStorage limits.
  write([item, ...list].slice(0, 12));
  return item;
}

export function deleteReport(id: string) {
  write(read().filter((r) => r.id !== id));
}
