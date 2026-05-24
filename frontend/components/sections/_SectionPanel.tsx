import type { StorymapSection } from "@/lib/storymap";

type Accent = "accent" | "warn" | "good" | "warm";

const accentBar: Record<Accent, string> = {
  accent: "bg-accent",
  warn: "bg-warn",
  good: "bg-good",
  warm: "bg-warm",
};

export default function SectionPanel({
  section,
  accent = "accent",
}: {
  section: StorymapSection;
  accent?: Accent;
}) {
  return (
    <div className="w-full">
      <div className={`h-1 w-12 mb-6 ${accentBar[accent]}`} />
      <h2 className="font-serif text-3xl leading-tight mb-4">{section.title}</h2>
      <div
        className="prose prose-stone text-ink/90 mb-6"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(section.description) }}
      />
      {Object.keys(section.kpis ?? {}).length > 0 && (
        <dl className="grid grid-cols-2 gap-4 mb-6">
          {Object.entries(section.kpis ?? {}).map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs uppercase tracking-wider text-muted">{k}</dt>
              <dd className="font-serif text-2xl">{v}</dd>
            </div>
          ))}
        </dl>
      )}
      {section.callouts && section.callouts.length > 0 && (
        <ul className="space-y-2 mb-2 text-sm">
          {section.callouts.map((c, i) => (
            <li key={i} className="border-l-2 border-muted/30 pl-3">
              {c}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Minimal markdown — bold (**…**) only, the rest is plain. Keep small.
function renderMarkdown(s: string): string {
  return escapeHtml(s).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
