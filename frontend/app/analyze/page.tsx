"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import AgentLog from "@/components/AgentLog";
import ArchetypePicker, { type Archetype } from "@/components/ArchetypePicker";

function AnalyzeInner() {
  const params = useSearchParams();
  const networkId = params.get("network");
  const [archetypes, setArchetypes] = useState<Archetype[] | null>(null);

  if (!networkId) {
    return <p className="text-warn">No network id in URL — start from the upload screen.</p>;
  }

  if (!archetypes) {
    return (
      <>
        <h1 className="font-serif text-3xl mb-2">What do you want to learn?</h1>
        <ArchetypePicker onSubmit={setArchetypes} />
      </>
    );
  }

  return (
    <>
      <h1 className="font-serif text-3xl mb-2">The agent is thinking…</h1>
      <p className="text-muted mb-6">
        Running <span className="text-ink font-medium">{archetypes.join(" + ")}</span>.
      </p>
      <AgentLog archetypes={archetypes} />
    </>
  );
}

export default function AnalyzePage() {
  return (
    <main className="min-h-screen px-6 py-12 max-w-3xl mx-auto">
      <Suspense fallback={<p className="text-muted">Loading…</p>}>
        <AnalyzeInner />
      </Suspense>
    </main>
  );
}
