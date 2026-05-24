"use client";

import { Suspense } from "react";
import AgentLog from "@/components/AgentLog";

export default function AnalyzePage() {
  return (
    <main className="min-h-screen px-6 py-12 max-w-3xl mx-auto">
      <h1 className="font-serif text-3xl mb-2">The agent is thinking…</h1>
      <p className="text-muted mb-8">
        Each step is a real decision: parse, classify, geocode, route, score, narrate.
      </p>
      <Suspense fallback={<p className="text-muted">Loading agent stream…</p>}>
        <AgentLog />
      </Suspense>
    </main>
  );
}
