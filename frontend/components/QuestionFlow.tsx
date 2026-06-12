"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight, Crosshair, Grid3X3, MapPin, Scale, Search, Sparkles, TrendingUp,
} from "lucide-react";
import type { Workflow } from "./WorkspacePanel";

/** One suggested question. Every preset runs a full analysis → report;
 *  the verbatim question steers the methodologist. */
interface Suggestion {
  icon: React.ComponentType<{ size?: number | string; className?: string }>;
  label: string;
  question: string;
  archetypes: Workflow[];
}

interface Props {
  /** Filename + row count for the header chip, e.g. "16 locations · branches.csv" */
  networkSummary: string;
  /** Run the analysis pipeline (methodologist → tools → report). */
  onAnalyze: (userIntent: string, archetypes: Workflow[]) => void;
  /** Free-text questions go to the chat agent instead. */
  onAskChat: (message: string) => void;
  onDismiss: () => void;
}

const SUGGESTIONS: Suggestion[] = [
  {
    icon: TrendingUp,
    label: "Diagnose performance",
    question: "How is my network performing — and which branches underperform their context?",
    archetypes: ["diagnose"],
  },
  {
    icon: MapPin,
    label: "Find where to expand",
    question: "Where should I open next? Show me the demand we don't reach yet.",
    archetypes: ["expand"],
  },
  {
    icon: Scale,
    label: "Rationalise the network",
    question: "Which branches overlap or cannibalise each other — what could we merge?",
    archetypes: ["rationalise"],
  },
  {
    icon: Crosshair,
    label: "Optimise coverage",
    question: "Where should I place 5 branches to cover the most residents?",
    archetypes: ["expand"],
  },
  {
    icon: Search,
    label: "Find look-alike areas",
    question: "Find locations similar to my best-performing branch.",
    archetypes: ["diagnose"],
  },
  {
    icon: Grid3X3,
    label: "Spot the whitespace",
    question: "Show me underserved whitespace — high demand far from any branch.",
    archetypes: ["expand"],
  },
];

/**
 * The post-upload moment: a liquid-glass card over the map that asks what
 * the user wants to find out — free-text first, six suggested intents below.
 * Replaces "pick one of three buttons" with a conversation starter.
 */
export default function QuestionFlow({ networkSummary, onAnalyze, onAskChat, onDismiss }: Props) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), 350);
    return () => clearTimeout(t);
  }, []);

  // Stagger the chips in after the card lands.
  const chips = useMemo(() => SUGGESTIONS, []);

  function pick(s: Suggestion) {
    onDismiss();
    onAnalyze(s.question, s.archetypes);
  }

  function submitFreeText() {
    const q = text.trim();
    if (!q) return;
    onDismiss();
    onAskChat(q);
  }

  return (
    <AnimatePresence>
      <motion.div
        className="absolute inset-0 z-30 flex items-center justify-center p-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
      >
        {/* scrim — soft, lets the map breathe through */}
        <motion.div
          className="absolute inset-0 bg-ink/10 backdrop-blur-[2px]"
          onClick={onDismiss}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        />
        <motion.div
          className="relative liquid-glass-strong rounded-2xl w-[44rem] max-w-[94%] px-9 py-8"
          initial={{ opacity: 0, y: 18, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.99 }}
          transition={{ duration: 0.35, ease: [0.21, 0.9, 0.27, 1] }}
        >
          <div className="flex items-center gap-2.5 mb-1">
            <span aria-hidden className="inline-block h-2 w-2 rounded-full accent-gradient" />
            <span className="text-[11px] uppercase tracking-wider text-muted">
              network loaded · {networkSummary}
            </span>
          </div>
          <h2 className="text-2xl md:text-[1.7rem] font-semibold tracking-tightish text-ink leading-tight mb-1.5">
            What would you like to find out?
          </h2>
          <p className="text-sm text-ink/70 mb-5 max-w-prose">
            Ask in plain language — tochka picks the methodology, runs the spatial
            analysis, and drops the evidence on the map.
          </p>

          {/* Free-text ask */}
          <form
            onSubmit={(e) => { e.preventDefault(); submitFreeText(); }}
            className="flex items-center gap-2 mb-6"
          >
            <div className="relative flex-1">
              <Sparkles size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-accent-500" aria-hidden />
              <input
                ref={inputRef}
                type="text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="e.g. which districts hold demand we don't serve yet?"
                className="w-full rounded-full border border-border bg-canvas/80 pl-10 pr-4 py-2.5 text-sm text-ink placeholder:text-subtle outline-none focus:border-accent-400 focus:ring-2 focus:ring-accent-100 transition"
              />
            </div>
            <button
              type="submit"
              disabled={!text.trim()}
              className="rounded-full accent-gradient text-canvas h-10 w-10 inline-flex items-center justify-center shadow-soft hover:shadow-pop disabled:opacity-40 disabled:cursor-not-allowed transition"
              aria-label="Ask"
            >
              <ArrowRight size={16} />
            </button>
          </form>

          {/* Suggested intents */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {chips.map((s, i) => {
              const Icon = s.icon;
              return (
                <motion.button
                  key={s.label}
                  type="button"
                  onClick={() => pick(s)}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.15 + i * 0.05, duration: 0.3, ease: "easeOut" }}
                  className="group text-left rounded-xl border border-border bg-canvas/70 hover:bg-canvas hover:border-accent-300 hover:shadow-card px-3.5 py-3 transition-all duration-200"
                  title={s.question}
                >
                  <Icon size={15} className="text-accent-500 mb-1.5 group-hover:scale-110 transition-transform duration-200" />
                  <div className="text-[13px] font-medium text-ink leading-snug">{s.label}</div>
                  <div className="text-[11px] text-muted mt-0.5 leading-snug line-clamp-2">{s.question}</div>
                </motion.button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={onDismiss}
            className="mt-5 text-[11px] text-muted hover:text-ink transition-colors"
          >
            skip — I&apos;ll explore the map first
          </button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
