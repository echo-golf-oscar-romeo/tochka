"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from "recharts";
import { BookmarkCheck, BookmarkPlus, Maximize2, Minimize2, X } from "lucide-react";
import type { ChartSpec, StorymapResult, StorymapSection } from "@/lib/storymap";

// House palette (tailwind tokens, hard-coded for chart fills).
const INK = "#0A0903";
const MUTED = "#5c5b56";
const BORDER = "#e7e6e2";
const ACCENT = "#4F35F8";
const SERIES = ["#4F35F8", "#37B2FA", "#FA8237", "#FB3640", "#C637FA", "#FAD037"];

const SECTION_ACCENTS: Record<string, string> = {
  "network-glance": "#4F35F8",
  "who-you-reach": "#37B2FA",
  "whats-working": "#FB3640",
  "opportunity": "#FA8237",
  "next-steps": "#4F35F8",
};

interface Props {
  spec: StorymapResult;
  open: boolean;
  saved: boolean;
  onSave: () => void;
  onClose: () => void;
}

/**
 * The report window: a right-hand slide-over that expands to a near-full
 * overlay. Renders the analysis as a designed document — numbered sections,
 * stat grids, charts chosen per SKILL_report's grammar, callout cards.
 */
export default function ReportPanel({ spec, open, saved, onSave, onClose }: Props) {
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const sections = spec.sections ?? [];

  useEffect(() => {
    if (!open) setExpanded(false);
  }, [open]);

  const date = useMemo(
    () => new Date().toLocaleDateString("en-HK", { day: "numeric", month: "long", year: "numeric" }),
    [],
  );

  function jumpTo(i: number) {
    const el = scrollRef.current?.querySelector(`[data-report-section="${i}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveIdx(i);
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="report-shell"
          className={`absolute inset-y-0 right-0 z-40 flex ${expanded ? "left-0 p-6" : "w-[46rem] max-w-[96%]"}`}
          initial={{ x: 48, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 48, opacity: 0 }}
          transition={{ duration: 0.32, ease: [0.21, 0.9, 0.27, 1] }}
        >
          {expanded && (
            <div className="absolute inset-0 bg-ink/15 backdrop-blur-[3px]" onClick={() => setExpanded(false)} />
          )}
          <motion.div
            layout
            className={`relative flex-1 flex flex-col bg-canvas border border-border overflow-hidden ${
              expanded ? "rounded-2xl shadow-pop" : "border-r-0 shadow-pop"
            }`}
            transition={{ duration: 0.32, ease: [0.21, 0.9, 0.27, 1] }}
          >
            {/* ---- Toolbar ---- */}
            <div className="shrink-0 flex items-center gap-1.5 px-5 py-3 border-b border-border liquid-glass">
              <span aria-hidden className="inline-block h-2 w-2 rounded-full accent-gradient mr-1" />
              <span className="text-[11px] uppercase tracking-wider text-muted flex-1">
                tochka · network report · {date}
              </span>
              <IconBtn
                title={saved ? "Saved to reports" : "Save to reports"}
                onClick={onSave}
                active={saved}
              >
                {saved ? <BookmarkCheck size={15} /> : <BookmarkPlus size={15} />}
              </IconBtn>
              <IconBtn title={expanded ? "Dock to side" : "Expand"} onClick={() => setExpanded((e) => !e)}>
                {expanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
              </IconBtn>
              <IconBtn title="Close report" onClick={onClose}>
                <X size={15} />
              </IconBtn>
            </div>

            <div className="flex-1 min-h-0 flex">
              {/* ---- Section nav (expanded only) ---- */}
              {expanded && (
                <nav className="hidden lg:flex w-56 shrink-0 flex-col gap-0.5 border-r border-border px-3 py-6">
                  {sections.map((s, i) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => jumpTo(i)}
                      className={`text-left rounded-lg px-3 py-2 text-[12.5px] leading-snug transition-colors ${
                        activeIdx === i ? "bg-accent-50 text-accent-700 font-medium" : "text-muted hover:text-ink hover:bg-rule"
                      }`}
                    >
                      <span className="tabular-nums mr-1.5 text-[11px] opacity-60">{String(i + 1).padStart(2, "0")}</span>
                      {s.title}
                    </button>
                  ))}
                </nav>
              )}

              {/* ---- Document ---- */}
              <div ref={scrollRef} className="flex-1 min-w-0 overflow-y-auto">
                <header className="px-8 pt-8 pb-7 border-b border-border">
                  <h1 className="text-2xl md:text-3xl font-semibold tracking-tightish text-ink leading-tight mb-2">
                    {spec.summary?.split(".")[0] ?? "Network report"}
                  </h1>
                  <p className="text-[13.5px] text-ink/70 max-w-prose leading-relaxed">{spec.summary}</p>
                </header>

                {sections.map((section, i) => (
                  <ReportSection
                    key={section.id}
                    section={section}
                    index={i}
                    accent={SECTION_ACCENTS[section.id] ?? ACCENT}
                    onInView={() => setActiveIdx(i)}
                  />
                ))}

                <footer className="px-8 py-8 text-[11px] text-muted border-t border-border">
                  Methodology + data: CSDI iGeoCom · Kontur population · OpenStreetMap ·
                  Mapbox isochrones · DuckDB-spatial. Generated by tochka.
                </footer>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function IconBtn({ title, onClick, active, children }: {
  title: string; onClick: () => void; active?: boolean; children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      className={`p-1.5 rounded-lg transition-colors ${
        active ? "text-accent-600 bg-accent-50" : "text-muted hover:text-ink hover:bg-rule"
      }`}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Section
// ---------------------------------------------------------------------------

function ReportSection({ section, index, accent, onInView }: {
  section: StorymapSection; index: number; accent: string; onInView: () => void;
}) {
  const ref = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && onInView()),
      { rootMargin: "-40% 0px -50% 0px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const kpis = Object.entries(section.kpis ?? {});
  const charts = section.charts ?? [];
  const callouts = section.callouts?.filter(Boolean) ?? [];

  return (
    <section ref={ref} data-report-section={index} className="px-8 py-7 border-b border-border last:border-b-0">
      <div className="flex items-baseline gap-3 mb-3">
        <span className="text-[11px] tabular-nums font-medium" style={{ color: accent }}>
          {String(index + 1).padStart(2, "0")}
        </span>
        <h2 className="text-lg md:text-xl font-semibold tracking-tightish text-ink">{section.title}</h2>
      </div>

      <div
        className="text-[13.5px] text-ink/85 leading-relaxed max-w-prose mb-5"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(section.description) }}
      />

      {kpis.length > 0 && (
        <dl className={`grid gap-x-6 gap-y-4 mb-6 ${kpis.length >= 3 ? "grid-cols-3" : "grid-cols-2"}`}>
          {kpis.map(([k, v]) => (
            <div key={k} className="border-l-2 pl-3" style={{ borderColor: accent }}>
              <dt className="text-[10px] uppercase tracking-wider text-muted">{k}</dt>
              <dd className="text-2xl md:text-[1.7rem] font-semibold text-ink tracking-tightish tabular-nums leading-none mt-1">
                {v}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {charts.length > 0 && (
        <div className={`grid gap-4 mb-5 ${charts.length > 1 ? "lg:grid-cols-2" : ""}`}>
          {charts.map((c, ci) => (
            <ChartBlock key={ci} spec={c} accent={accent} />
          ))}
        </div>
      )}

      {callouts.length > 0 && (
        <ul className="space-y-2">
          {callouts.map((c, ci) => (
            <li
              key={ci}
              className="rounded-xl border border-border bg-surface px-4 py-3 text-[12.5px] text-ink/90 leading-relaxed"
            >
              <span className="inline-block h-1.5 w-1.5 rounded-full mr-2 align-middle" style={{ background: accent }} aria-hidden />
              {c}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Charts — one component per kind, per the report-design grammar
// ---------------------------------------------------------------------------

function ChartBlock({ spec, accent }: { spec: ChartSpec; accent: string }) {
  return (
    <figure className="rounded-xl border border-border bg-canvas p-4">
      <figcaption className="mb-3">
        <div className="text-[13px] font-medium text-ink leading-snug">{spec.title}</div>
        {spec.subtitle && <div className="text-[11px] text-muted mt-0.5">{spec.subtitle}</div>}
      </figcaption>
      {spec.kind === "bar" && <BarBlock spec={spec} accent={accent} />}
      {spec.kind === "donut" && <DonutBlock spec={spec} />}
      {spec.kind === "scatter" && <ScatterBlock spec={spec} accent={accent} />}
      {(spec.kind === "rank" || spec.kind === "area") && <RankBlock spec={spec} accent={accent} />}
      {spec.source && (
        <div className="mt-2.5 text-[10px] text-subtle">source · {spec.source}</div>
      )}
    </figure>
  );
}

const fmt = (n: number) => (Math.abs(n) >= 1000 ? n.toLocaleString("en-US") : String(n));

const tooltipStyle = {
  fontSize: 11.5,
  borderRadius: 8,
  border: `1px solid ${BORDER}`,
  boxShadow: "0 8px 24px -8px rgba(10,9,3,0.15)",
  padding: "6px 10px",
};

function BarBlock({ spec, accent }: { spec: ChartSpec; accent: string }) {
  const data = spec.data.slice(0, 8);
  const h = Math.max(120, data.length * 30);
  return (
    <div style={{ height: h }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 36, left: 0, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category" dataKey="label" width={108}
            tick={{ fontSize: 11, fill: MUTED }} axisLine={false} tickLine={false}
          />
          <Tooltip cursor={{ fill: "rgba(10,9,3,0.04)" }} contentStyle={tooltipStyle}
                   formatter={(v) => [`${fmt(Number(v))}${spec.unit ? ` ${spec.unit}` : ""}`, ""]} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={16}
               label={{ position: "right", fontSize: 10.5, fill: MUTED,
                        formatter: (v) => fmt(Number(v ?? 0)) }}>
            {data.map((_, i) => (
              <Cell key={i} fill={accent} fillOpacity={1 - i * 0.09} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function DonutBlock({ spec }: { spec: ChartSpec }) {
  const data = spec.data.slice(0, 6);
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  return (
    <div className="flex items-center gap-4">
      <div className="h-36 w-36 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="label" innerRadius={42} outerRadius={64}
                 paddingAngle={2} strokeWidth={0}>
              {data.map((_, i) => <Cell key={i} fill={SERIES[i % SERIES.length]} />)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle}
                     formatter={(v, n) => [`${fmt(Number(v))} (${Math.round((Number(v) / total) * 100)}%)`, n]} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="flex-1 min-w-0 space-y-1.5">
        {data.map((d, i) => (
          <li key={d.label} className="flex items-center gap-2 text-[11.5px]">
            <span className="inline-block h-2.5 w-2.5 rounded-[3px] shrink-0" style={{ background: SERIES[i % SERIES.length] }} />
            <span className="text-ink/85 truncate flex-1">{d.label}</span>
            <span className="text-muted tabular-nums">{Math.round((d.value / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ScatterBlock({ spec, accent }: { spec: ChartSpec; accent: string }) {
  const data = spec.data.map((d) => ({ ...d, x: d.value, y: d.value2 ?? 0 }));
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
          <XAxis type="number" dataKey="x" name="expected" tick={{ fontSize: 10, fill: MUTED }}
                 axisLine={{ stroke: BORDER }} tickLine={false} tickFormatter={fmt} />
          <YAxis type="number" dataKey="y" name="actual" tick={{ fontSize: 10, fill: MUTED }}
                 axisLine={{ stroke: BORDER }} tickLine={false} tickFormatter={fmt} width={48} />
          <Tooltip
            cursor={{ strokeDasharray: "3 3", stroke: MUTED }}
            contentStyle={tooltipStyle}
            formatter={(v, name) => [fmt(Number(v)), name === "x" ? "expected" : "actual"]}
            labelFormatter={() => ""}
          />
          <Scatter data={data} fill={accent} fillOpacity={0.85} stroke={INK} strokeOpacity={0.15} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Ordered list with inline value bars — crisper than a chart for top-N lists. */
function RankBlock({ spec, accent }: { spec: ChartSpec; accent: string }) {
  const data = spec.data.slice(0, 8);
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <ol className="space-y-2">
      {data.map((d, i) => (
        <li key={d.label} className="flex items-center gap-2.5 text-[12px]">
          <span className="w-4 text-right tabular-nums text-subtle">{i + 1}</span>
          <span className="w-28 truncate text-ink/85" title={d.label}>{d.label}</span>
          <span className="flex-1 h-1.5 rounded-full bg-rule overflow-hidden">
            <motion.span
              className="block h-full rounded-full"
              style={{ background: accent }}
              initial={{ width: 0 }}
              whileInView={{ width: `${(d.value / max) * 100}%` }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.06, ease: "easeOut" }}
            />
          </span>
          <span className="w-14 text-right tabular-nums text-muted">
            {fmt(d.value)}{spec.unit === "%" ? "%" : ""}
          </span>
        </li>
      ))}
    </ol>
  );
}

// Minimal markdown — bold only.
function renderMarkdown(s: string): string {
  return escapeHtml(s).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
