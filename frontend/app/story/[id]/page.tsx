"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import Storymap from "@/components/Storymap";
import { fetchStorymap } from "@/lib/api";
import type { StorymapResult } from "@/lib/storymap";

export default function StoryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<StorymapResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchStorymap(id).then(setData).catch((e) => setErr(String(e)));
  }, [id]);

  if (err) {
    return (
      <main className="min-h-screen bg-canvas">
        <BackBar />
        <div className="p-12 text-accent-700">Failed to load: {err}</div>
      </main>
    );
  }
  if (!data) {
    return (
      <main className="min-h-screen bg-canvas">
        <BackBar />
        <div className="p-12 text-muted">Loading storymap…</div>
      </main>
    );
  }
  return (
    <>
      <BackBar />
      <Storymap data={data} />
    </>
  );
}


function BackBar() {
  return (
    <div className="fixed top-3 left-3 z-50">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 rounded-full bg-canvas/95 backdrop-blur border border-border shadow-card px-3 py-1.5 text-xs text-ink hover:text-accent-600 hover:border-accent-300 transition"
      >
        ← Workspace
      </Link>
    </div>
  );
}
