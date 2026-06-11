import Link from "next/link";

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-surface">
      <div className="mx-auto max-w-prose px-6 py-16">
        <Link
          href="/"
          className="text-xs text-muted hover:text-ink inline-flex items-center gap-1.5"
        >
          ← Back to workspace
        </Link>

        <h1 className="display text-5xl mt-8 mb-3 lowercase">tochka</h1>
        <p className="text-lg text-muted leading-relaxed mb-8">
          Agent-driven location intelligence for Hong Kong banking, retail, and
          social-services networks. Upload a CSV of locations, pick a workflow,
          let the agent reason over Hong Kong&apos;s public spatial data, and
          read the result as a map, a storymap, or a conversation.
        </p>

        <Section title="What it does">
          <ul className="space-y-1.5">
            <li><strong>Diagnose</strong> — how the existing network performs against catchment population and competitive pressure.</li>
            <li><strong>Expand</strong> — where to open next, ranked by uncovered demand.</li>
            <li><strong>Rationalise</strong> — which locations to close, merge, or resize.</li>
            <li><strong>Ask the data</strong> — natural-language spatial SQL over the loaded network, the HK competitor table, and 37k official CSDI POIs.</li>
            <li><strong>Optimise</strong> — p-median / LSCP / MCLP coverage optimisation, whitespace gaps, best-new-site ranking.</li>
            <li><strong>Explain</strong> — LISA hot spots, look-alike similarity search, drivers regression, and a designed report with charts and recommendations.</li>
          </ul>
        </Section>

        <Section title="Under the hood">
          <p>
            FastAPI + DuckDB-spatial for the analysis layer, with PuLP/CBC for
            coverage optimisation and scikit-learn for embeddings and drivers.
            MapLibre GL for the canvas. Qwen / DeepSeek for the agentic
            reasoning. Mapbox for walking isochrones. OpenStreetMap for the
            ~1,300 HK bank and ATM locations; CSDI iGeoCom for 37k official
            POIs; Kontur for the H3 population grid; CSDI Address Lookup
            Service for geocoding addresses that arrive without coordinates.
          </p>
        </Section>

        <Section title="Submission targets">
          <p>
            Built for two parallel Hong Kong submissions in May 2026: the HKSTP
            Spatial AI Sandbox PoC Challenge and Qwenched #1 (WYB × Alibaba
            Cloud). Both rely on the same product surface.
          </p>
        </Section>

        <Section title="Honest scope">
          <p>
            Some pieces remain pragmatic: the Kontur population grid stands in
            for CSDI&apos;s Population Distribution FSDT; coverage optimisation
            time-boxes the CBC solver and falls back to a greedy heuristic on
            big inputs; per-task agentic planning is on the roadmap but the
            workflow tool sequence is currently deterministic.
          </p>
        </Section>

        <div className="mt-12 pt-6 border-t border-border text-xs text-muted">
          shults &amp; partners · 2026
        </div>
      </div>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="text-base text-ink font-semibold mb-2">{title}</h2>
      <div className="text-sm text-ink/80 leading-relaxed">{children}</div>
    </section>
  );
}
