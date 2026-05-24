"use client";

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

  if (err) return <main className="p-12 text-warn">Failed to load: {err}</main>;
  if (!data) return <main className="p-12 text-muted">Loading storymap…</main>;
  return <Storymap data={data} />;
}
