"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { StorymapSection } from "@/lib/storymap";

type Accent = "accent" | "warn" | "good" | "warm";

const accentColour: Record<Accent, string> = {
  accent: "#4F35F8",   // primary purple
  warn:   "#FB3640",   // secondary red
  good:   "#37FA7E",   // green
  warm:   "#FA8237",   // orange
};

interface Props {
  section: StorymapSection;
  accent?: Accent;
  /** Fired when the user clicks "View on map" — Storymap fits the map to
   *  this section's centre / zoom. */
  onFitToSection?: () => void;
}

export default function SectionPanel({
  section, accent = "accent", onFitToSection,
}: Props) {
  const colour = accentColour[accent];
  const kpiEntries = Object.entries(section.kpis ?? {});

  // Recharts data: parse KPI values into numbers so a section with multiple
  // numeric KPIs becomes a small bar chart underneath the description.
  const chartData = useMemo(() => {
    return kpiEntries
      .map(([k, v]) => ({ label: k, value: parseNumber(v) }))
      .filter((d) => d.value !== null) as { label: string; value: number }[];
  }, [kpiEntries]);

  return (
    <div className="w-full">
      <div className="h-1 w-12 mb-6 rounded-full" style={{ background: colour }} />
      <h2 className="text-3xl md:text-4xl font-semibold tracking-tightish text-ink mb-4 leading-tight">
        {section.title}
      </h2>

      <div
        className="prose prose-stone max-w-prose text-ink/85 mb-7 text-[15px] leading-relaxed"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(section.description) }}
      />

      {kpiEntries.length > 0 && (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-5 mb-7">
          {kpiEntries.map(([k, v]) => (
            <KpiCard key={k} label={k} value={v} colour={colour} />
          ))}
        </dl>
      )}

      {chartData.length >= 2 && (
        <div className="mb-7 rounded-lg border border-border bg-canvas p-3">
          <div className="text-[10px] uppercase tracking-wider text-muted mb-2">
            Chart of KPIs above
          </div>
          <div className="h-32 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 16 }}>
                <XAxis
                  dataKey="label"
                  fontSize={10}
                  tick={{ fill: "#5c5b56" }}
                  axisLine={false}
                  tickLine={false}
                  angle={-12}
                  textAnchor="end"
                  height={36}
                />
                <YAxis hide />
                <Tooltip
                  cursor={{ fill: "rgba(10,9,3,0.04)" }}
                  contentStyle={{ fontSize: 11, borderRadius: 4, border: "1px solid #e7e6e2" }}
                />
                <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={colour} fillOpacity={0.85 - i * 0.05} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {section.callouts && section.callouts.length > 0 && (
        <ul className="space-y-2 mb-6">
          {section.callouts.map((c, i) => (
            <li
              key={i}
              className="rounded-lg border border-border bg-surface px-4 py-3 text-sm text-ink/90 hover:border-accent-300 transition"
            >
              <span className="inline-block h-1.5 w-1.5 rounded-full mr-2 align-middle"
                    style={{ background: colour }} aria-hidden />
              {c}
            </li>
          ))}
        </ul>
      )}

      {onFitToSection && (
        <button
          type="button"
          onClick={onFitToSection}
          className="inline-flex items-center gap-2 rounded-full border border-border hover:border-accent-300 bg-canvas hover:bg-accent-50 px-3.5 py-1.5 text-xs text-ink transition"
        >
          <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: colour }} />
          Re-centre map on this view
        </button>
      )}
    </div>
  );
}

// -- KpiCard: animated count-up for numeric values, big bold number ----------

interface KpiCardProps {
  label: string;
  value: string;
  colour: string;
}

function KpiCard({ label, value, colour }: KpiCardProps) {
  const numeric = parseNumber(value);
  const [displayed, setDisplayed] = useState(numeric === null ? value : "0");
  const animatedRef = useRef(false);
  const isFinal = numeric === null;

  useEffect(() => {
    if (isFinal) {
      setDisplayed(value);
      return;
    }
    if (animatedRef.current) return;
    animatedRef.current = true;
    const target = numeric!;
    const duration = 700;
    const start = performance.now();
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - k, 3);
      const v = Math.round(target * eased);
      setDisplayed(formatLikeOriginal(value, v));
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [value, numeric, isFinal]);

  return (
    <div className="border-l-2 pl-3" style={{ borderColor: colour }}>
      <dt className="text-[10px] uppercase tracking-wider text-muted">{label}</dt>
      <dd className="text-3xl md:text-4xl font-semibold text-ink tracking-tightish tabular-nums leading-none mt-1">
        {displayed}
      </dd>
    </div>
  );
}

function parseNumber(s: string): number | null {
  if (!s) return null;
  // Strip commas / whitespace / suffixes; preserve sign.
  const cleaned = s.replace(/[,\s]/g, "");
  const m = cleaned.match(/^-?\d+(\.\d+)?/);
  if (!m) return null;
  const n = parseFloat(m[0]);
  return Number.isFinite(n) ? n : null;
}

/** Re-format an in-progress count-up to look like the original string. */
function formatLikeOriginal(original: string, n: number): string {
  if (/^[\d,\.]+$/.test(original.trim())) {
    // Pure number — comma-group thousands like the original did.
    return n.toLocaleString();
  }
  // Suffix-aware: preserve trailing non-digit text (e.g. " residents", "%").
  const m = original.match(/^[-\d,\.\s]+(.*)$/);
  const suffix = m ? m[1] : "";
  return `${n.toLocaleString()}${suffix}`;
}

// Minimal markdown — bold (**…**) only.
function renderMarkdown(s: string): string {
  return escapeHtml(s).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
