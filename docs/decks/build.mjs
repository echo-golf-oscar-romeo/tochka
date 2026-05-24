// Tochka HKSTP decks — proposal + business plan.
//
// Run: node docs/decks/build.mjs
// Output: docs/decks/proposal.pptx, docs/decks/business_plan.pptx
//
// Design language:
// - LAYOUT_16x9, paper background (Aino-inspired), serif titles (Georgia),
//   sans-serif body (Calibri/Inter).
// - Every slide has a small "chapter marker" dot in the upper-right with the
//   slide index — a visual echo of the storymap's chapter dots.
// - Three pre-generated PNG figures (see docs/figures_gen.py) carry the
//   BOCHK problem narrative; everything else is shapes + text so it stays
//   editable in PowerPoint.
//
// All figures and quantitative claims about BOCHK are clearly labelled
// "Illustrative — synthetic data" inside each PNG. The deck text is also
// careful to frame the sandbox as the engagement to *produce* validated
// numbers, not to claim them up front.

import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

// pptxgenjs 4.x ships an ESM build, but its own package.json doesn't set
// type:module, so Node refuses to load it through ESM resolution. Importing
// via createRequire picks up the CJS build, which works cleanly.
const require = createRequire(import.meta.url);
const pptxgen = require("pptxgenjs");

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIG = path.resolve(__dirname, "..", "figures");

// --------- palette ----------
const P = {
  paper:  "F6F4EF",
  ink:    "1A1A1A",
  muted:  "6B6760",
  hair:   "DAD6CC", // muted divider line
  accent: "0F5EA8",
  warm:   "E07A5F",
  warn:   "C44536",
  good:   "3A7D44",
};

const FONT_SERIF = "Georgia";
const FONT_SANS  = "Calibri";

// --------- helpers ----------
function shadow() {
  return { type: "outer", color: "000000", blur: 8, offset: 2, angle: 90, opacity: 0.10 };
}

function eyebrow(slide, text, x = 0.5, y = 0.32) {
  slide.addText(text.toUpperCase(), {
    x, y, w: 9, h: 0.25,
    fontFace: FONT_SANS, fontSize: 10, bold: true, color: P.accent,
    charSpacing: 4, margin: 0,
  });
}

function title(slide, text, x = 0.5, y = 0.6, w = 9, h = 0.9) {
  slide.addText(text, {
    x, y, w, h,
    fontFace: FONT_SERIF, fontSize: 32, bold: true, color: P.ink, margin: 0,
  });
}

function body(slide, text, opts = {}) {
  const { x = 0.5, y = 1.8, w = 9, h = 3, fontSize = 15, color = P.ink } = opts;
  slide.addText(text, { x, y, w, h, fontFace: FONT_SANS, fontSize, color, paraSpaceAfter: 6 });
}

function chapterMarker(slide, idx, total) {
  // Subtle chapter dots running across top-right — references the storymap UX.
  const totalW = 1.6;
  const cellW = totalW / total;
  const startX = 9.55 - totalW;
  const y = 0.35;
  for (let i = 1; i <= total; i++) {
    const cx = startX + (i - 0.5) * cellW;
    const isActive = i === idx;
    slide.addShape("ellipse", {
      x: cx - 0.045, y: y - 0.045, w: 0.09, h: 0.09,
      fill: { color: isActive ? P.accent : P.hair },
      line: { color: isActive ? P.accent : P.hair, width: 0 },
    });
  }
  slide.addText(`${idx} / ${total}`, {
    x: startX - 0.6, y: y - 0.12, w: 0.55, h: 0.3,
    fontFace: FONT_SANS, fontSize: 9, color: P.muted, align: "right", margin: 0,
  });
}

function footer(slide, text) {
  slide.addText(text, {
    x: 0.5, y: 5.25, w: 9, h: 0.2,
    fontFace: FONT_SANS, fontSize: 8, color: P.muted, italic: true, margin: 0,
  });
}

function baseSlide(pres, idx, total) {
  const s = pres.addSlide();
  s.background = { color: P.paper };
  chapterMarker(s, idx, total);
  return s;
}

// =============================================================================
// PROPOSAL DECK
// =============================================================================
async function buildProposal() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "Tochka — HKSTP Spatial AI Sandbox Proposal";
  pres.author = "shults & partners";

  const N = 12;
  let idx = 0;

  // --- 1. Title slide -------------------------------------------------------
  idx++;
  {
    const s = pres.addSlide();
    s.background = { color: P.paper };
    s.addText("TOCHKA", {
      x: 0.6, y: 0.5, w: 6, h: 0.4,
      fontFace: FONT_SANS, fontSize: 12, bold: true, color: P.accent,
      charSpacing: 8, margin: 0,
    });
    s.addText("Agent-driven location intelligence", {
      x: 0.6, y: 1.5, w: 8.5, h: 1.4,
      fontFace: FONT_SERIF, fontSize: 44, bold: true, color: P.ink, margin: 0,
    });
    s.addText("for Hong Kong banking — a proposal to the HKSTP Spatial AI Sandbox", {
      x: 0.6, y: 2.95, w: 8.5, h: 0.6,
      fontFace: FONT_SANS, fontSize: 18, color: P.muted, italic: true, margin: 0,
    });
    // Bottom row — partner, team, date
    s.addText([
      { text: "Corporate partner ", options: { color: P.muted } },
      { text: "Bank of China (Hong Kong)", options: { bold: true, color: P.ink, breakLine: true } },
      { text: "Team ", options: { color: P.muted } },
      { text: "shults & partners", options: { bold: true, color: P.ink, breakLine: true } },
      { text: "Submitted ", options: { color: P.muted } },
      { text: "26 May 2026", options: { bold: true, color: P.ink } },
    ], {
      x: 0.6, y: 4.4, w: 9, h: 0.9,
      fontFace: FONT_SANS, fontSize: 12, paraSpaceAfter: 4, margin: 0,
    });
    // Subtle storymap-dot motif lower-left
    for (let i = 0; i < 5; i++) {
      s.addShape("ellipse", {
        x: 0.6 + i * 0.18, y: 5.25, w: 0.09, h: 0.09,
        fill: { color: i === 0 ? P.accent : P.hair },
        line: { color: i === 0 ? P.accent : P.hair, width: 0 },
      });
    }
  }

  // --- 2. Why now -----------------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "The opening");
    title(s, "Why now");
    // Three-column rationale, no bullets
    const cols = [
      {
        kicker: "DEMAND HAS MOVED",
        body: "Hong Kong branch and ATM networks were sized for a population that has shifted. New residential growth, ageing in place, and post-2020 mobility patterns have changed who lives within a 10-minute walk of every branch.",
      },
      {
        kicker: "PUBLIC SPATIAL DATA IS READY",
        body: "CSDI now publishes the 3D Pedestrian Network, full HK Population Distribution (Mar 2025), and iGeoCom — enough depth to drive real catchment analysis without licensing private datasets.",
      },
      {
        kicker: "AGENTS CAN ORCHESTRATE THIS",
        body: "Single-LLM tools are not enough — spatial analysis needs methodology selection, tool sequencing, and narrative synthesis. Qwen-class agents finally do this reliably.",
      },
    ];
    cols.forEach((c, i) => {
      const x = 0.5 + i * 3.05;
      s.addText(c.kicker, {
        x, y: 1.8, w: 2.9, h: 0.3,
        fontFace: FONT_SANS, fontSize: 10, bold: true, color: P.accent, charSpacing: 3, margin: 0,
      });
      s.addText(c.body, {
        x, y: 2.15, w: 2.9, h: 2.6,
        fontFace: FONT_SANS, fontSize: 13.5, color: P.ink, paraSpaceAfter: 4, margin: 0,
      });
    });
  }

  // --- 3. BOCHK's problem in three pictures — intro -------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "The customer problem");
    title(s, "BOCHK's challenge in three pictures");
    body(s,
      "Three independent narratives, one shared root cause: the bank lacks a spatial intelligence layer that ties branch operations to the city it serves. The next three slides illustrate what Tochka would surface during a 12-week sandbox engagement.",
      { y: 1.7, h: 1.2, fontSize: 16 }
    );
    // Three preview cards
    const items = [
      { num: "A", t: "Branch coverage", c: "Where the network misses high-density residential zones." },
      { num: "B", t: "Queue pressure",  c: "Which branches run hot at peak hour despite identical staffing." },
      { num: "C", t: "Wealth affinity", c: "Where premium-POI density and transaction value diverge." },
    ];
    items.forEach((it, i) => {
      const x = 0.5 + i * 3.05;
      s.addShape("rect", {
        x, y: 3.3, w: 2.9, h: 1.7,
        fill: { color: "FFFFFF" }, line: { color: P.hair, width: 0.75 },
        shadow: shadow(),
      });
      s.addShape("ellipse", {
        x: x + 0.25, y: 3.5, w: 0.5, h: 0.5,
        fill: { color: P.accent }, line: { color: P.accent, width: 0 },
      });
      s.addText(it.num, {
        x: x + 0.25, y: 3.5, w: 0.5, h: 0.5,
        fontFace: FONT_SERIF, fontSize: 20, bold: true, color: "FFFFFF",
        align: "center", valign: "middle", margin: 0,
      });
      s.addText(it.t, {
        x: x + 0.9, y: 3.55, w: 1.9, h: 0.4,
        fontFace: FONT_SERIF, fontSize: 18, bold: true, color: P.ink, margin: 0,
      });
      s.addText(it.c, {
        x: x + 0.25, y: 4.15, w: 2.45, h: 0.8,
        fontFace: FONT_SANS, fontSize: 12, color: P.muted, margin: 0,
      });
    });
    footer(s, "All three pictures use illustrative synthetic data — real BOCHK figures emerge during the sandbox engagement.");
  }

  // --- 4. Picture A — coverage gaps -----------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Picture A · branch coverage");
    title(s, "Where the network misses dense residential demand");
    s.addImage({
      path: path.join(FIG, "fig_01_coverage_gaps.png"),
      x: 0.5, y: 1.55, w: 9, h: 3.4, sizing: { type: "contain", w: 9, h: 3.4 },
    });
    body(s,
      [
        { text: "Catchments built on the CSDI 3D Pedestrian Network ", options: { bold: true } },
        { text: "— not crow-flies circles — make the gap obvious and rankable. The agent ranks every 250m cell in HK by uncovered demand and shortlists the top five candidate locations." },
      ],
      { y: 4.45, h: 0.6, fontSize: 12.5, color: P.muted }
    );
  }

  // --- 5. Picture B — queue pressure ----------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Picture B · queue pressure");
    title(s, "Same staffing, very different load");
    s.addImage({
      path: path.join(FIG, "fig_02_queue_pressure.png"),
      x: 0.5, y: 1.55, w: 9, h: 3.4, sizing: { type: "contain", w: 9, h: 3.4 },
    });
    body(s,
      [
        { text: "Demand-weighted staffing ", options: { bold: true } },
        { text: "follows from the same catchment data: spatio-temporal load profiles per branch let the agent recommend differential staffing or capacity rebalancing without site visits." },
      ],
      { y: 4.45, h: 0.6, fontSize: 12.5, color: P.muted }
    );
  }

  // --- 6. Picture C — wealth affinity ---------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Picture C · wealth prospecting");
    title(s, "Premium POI density predicts transaction value");
    s.addImage({
      path: path.join(FIG, "fig_03_wealth_affinity.png"),
      x: 0.5, y: 1.55, w: 9, h: 3.4, sizing: { type: "contain", w: 9, h: 3.4 },
    });
    body(s,
      [
        { text: "Spatial wealth segmentation ", options: { bold: true } },
        { text: "from POI affinity scoring — private clubs, specialty hospitals, international schools — gives Private Banking a city-wide prospecting map without touching customer PII." },
      ],
      { y: 4.45, h: 0.6, fontSize: 12.5, color: P.muted }
    );
  }

  // --- 7. The product in one screen -----------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "The product");
    title(s, "Upload a CSV. Read a storymap.");

    // Left — schematic of the storymap UX (sticky map + scrolling chapters)
    s.addShape("rect", { x: 0.5, y: 1.6, w: 4.5, h: 3.4, fill: { color: "FFFFFF" }, line: { color: P.hair, width: 0.75 }, shadow: shadow() });
    // "Map" half
    s.addShape("rect", { x: 0.5, y: 1.6, w: 2.6, h: 3.4, fill: { color: "EFEDE6" }, line: { color: "EFEDE6", width: 0 } });
    // sprinkle accent dots (branches) on map
    const dotXY = [[1.0, 2.0], [1.4, 2.4], [1.9, 2.2], [2.3, 2.8], [1.2, 3.2], [2.1, 3.4], [1.6, 3.7], [2.5, 3.6], [1.0, 4.0], [2.2, 4.3]];
    dotXY.forEach(([dx, dy]) => {
      s.addShape("ellipse", { x: dx, y: dy, w: 0.12, h: 0.12, fill: { color: P.accent }, line: { color: P.accent, width: 0 } });
    });
    // hex sprinkle to suggest density
    [[1.3, 2.3], [1.7, 3.0], [2.0, 3.3], [1.5, 4.1]].forEach(([hx, hy]) => {
      s.addShape("ellipse", { x: hx, y: hy, w: 0.18, h: 0.18, fill: { color: P.warm, transparency: 50 }, line: { color: P.warm, width: 0 } });
    });
    // "Chapter" half
    s.addText("Your network at a glance", {
      x: 3.25, y: 1.8, w: 1.6, h: 0.4,
      fontFace: FONT_SERIF, fontSize: 11, bold: true, color: P.ink, margin: 0,
    });
    s.addText("30 branches across 9 districts.", {
      x: 3.25, y: 2.2, w: 1.6, h: 0.4,
      fontFace: FONT_SANS, fontSize: 9, color: P.muted, margin: 0,
    });
    s.addText("Within a 10-min walk of 1.2M residents.", {
      x: 3.25, y: 2.65, w: 1.6, h: 0.4,
      fontFace: FONT_SANS, fontSize: 9, color: P.muted, margin: 0,
    });
    s.addText("Three underperformers vs Huff baseline.", {
      x: 3.25, y: 3.1, w: 1.6, h: 0.4,
      fontFace: FONT_SANS, fontSize: 9, color: P.muted, margin: 0,
    });
    s.addText("Top five candidate openings ranked.", {
      x: 3.25, y: 3.55, w: 1.6, h: 0.4,
      fontFace: FONT_SANS, fontSize: 9, color: P.muted, margin: 0,
    });
    // active chapter marker on the right column
    s.addShape("ellipse", { x: 3.13, y: 1.88, w: 0.08, h: 0.08, fill: { color: P.accent }, line: { color: P.accent, width: 0 } });

    // Right — the five storymap sections list
    s.addText("FIVE SECTIONS", {
      x: 5.4, y: 1.65, w: 4, h: 0.3,
      fontFace: FONT_SANS, fontSize: 10, bold: true, color: P.accent, charSpacing: 3, margin: 0,
    });
    const sections = [
      ["1", "Your network at a glance", "summary KPIs + location map"],
      ["2", "Who you reach today",      "isochrones + population captured"],
      ["3", "What's working, what's not", "anomaly detection on Huff baseline"],
      ["4", "Where the opportunity is", "ranked gap-analysis hex map"],
      ["5", "Next steps",                "concrete actions, click-to-rationale"],
    ];
    sections.forEach((sec, i) => {
      const yy = 2.05 + i * 0.62;
      s.addShape("ellipse", {
        x: 5.4, y: yy, w: 0.32, h: 0.32, fill: { color: P.accent }, line: { color: P.accent, width: 0 },
      });
      s.addText(sec[0], {
        x: 5.4, y: yy, w: 0.32, h: 0.32,
        fontFace: FONT_SERIF, fontSize: 13, bold: true, color: "FFFFFF",
        align: "center", valign: "middle", margin: 0,
      });
      s.addText(sec[1], {
        x: 5.85, y: yy - 0.05, w: 3.6, h: 0.32,
        fontFace: FONT_SERIF, fontSize: 13, bold: true, color: P.ink, margin: 0,
      });
      s.addText(sec[2], {
        x: 5.85, y: yy + 0.2, w: 3.6, h: 0.3,
        fontFace: FONT_SANS, fontSize: 10.5, color: P.muted, margin: 0,
      });
    });

    footer(s, "Schematic. Live UI uses MapLibre + CSDI Vector basemap, scroll-driven via the Mapbox Storytelling pattern.");
  }

  // --- 8. How the agent thinks — 4 questions diagram ------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Methodology");
    title(s, "How the agent thinks — four questions, in order");

    const qs = [
      { num: "1", t: "Your network",  d: "POI type, geographic extent, geocoding via CSDI ALS." },
      { num: "2", t: "Demand model",  d: "People-driven, visit-driven, flow-driven, or catchment-fixed." },
      { num: "3", t: "Analytical question", d: "Diagnose · Expand · Rationalise. Composable." },
      { num: "4", t: "Data plan",     d: "User fields → CSDI → parsed GMaps → OSM fallback." },
    ];
    qs.forEach((q, i) => {
      const x = 0.5 + i * 2.3;
      // numbered disc
      s.addShape("ellipse", { x: x + 0.85, y: 1.85, w: 0.7, h: 0.7,
        fill: { color: P.accent }, line: { color: P.accent, width: 0 } });
      s.addText(q.num, { x: x + 0.85, y: 1.85, w: 0.7, h: 0.7,
        fontFace: FONT_SERIF, fontSize: 26, bold: true, color: "FFFFFF",
        align: "center", valign: "middle", margin: 0 });
      // arrow to next (except last)
      if (i < qs.length - 1) {
        s.addShape("line", {
          x: x + 1.7, y: 2.2, w: 0.6, h: 0,
          line: { color: P.muted, width: 1.5, endArrowType: "triangle" },
        });
      }
      s.addText(q.t, { x, y: 2.75, w: 2.2, h: 0.4,
        fontFace: FONT_SERIF, fontSize: 16, bold: true, color: P.ink,
        align: "center", margin: 0 });
      s.addText(q.d, { x, y: 3.2, w: 2.2, h: 1.3,
        fontFace: FONT_SANS, fontSize: 12, color: P.muted,
        align: "center", margin: 0 });
    });
    s.addText("Tools are deterministic Python functions. The LLM picks tools and reads results — it does not do the math.", {
      x: 0.5, y: 4.7, w: 9, h: 0.4,
      fontFace: FONT_SANS, fontSize: 12, italic: true, color: P.ink, align: "center", margin: 0,
    });
  }

  // --- 9. CSDI inside -------------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Public data inside");
    title(s, "CSDI is the spine of every analysis");

    const rows = [
      ["Storymap section", "CSDI Map APIs", "CSDI datasets / FSDTs"],
      ["1. Your network at a glance", "Vector Map (basemap)", "ALS (Address Lookup), iGeoCom"],
      ["2. Who you reach today",       "3D Pedestrian Route Search", "Population Distribution (Mar 2025), 3D Pedestrian Network"],
      ["3. What's working, what's not", "Search Nearby", "Building footprints, iGeoCom"],
      ["4. Where the opportunity is",  "Location Search, Identify", "Population Distribution, Streetscape 360"],
      ["5. Next steps",                 "Streetscape 360 (drill-in)",  "3D Visualisation Map (HK-wide)"],
    ];
    s.addTable(rows, {
      x: 0.5, y: 1.7, w: 9, colW: [2.4, 2.6, 4],
      fontFace: FONT_SANS, fontSize: 11.5, color: P.ink,
      border: { type: "solid", pt: 0.5, color: P.hair },
      rowH: 0.55,
    });
    // Style header row in code-side note (pptxgenjs styling requires per-cell options for richer table)
    s.addText("CSDI Map APIs and FSDT datasets account for 50% of HKSTP's assessment weight. This proposal commits to using them as primary sources, not fallbacks.", {
      x: 0.5, y: 4.8, w: 9, h: 0.5,
      fontFace: FONT_SANS, fontSize: 12, italic: true, color: P.muted, margin: 0,
    });
  }

  // --- 10. Sandbox plan -----------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Engagement");
    title(s, "12-week sandbox plan");
    const rows = [
      ["Weeks", "Milestone", "Outputs"],
      ["1–2",   "BOCHK data intake, methodology lock-in", "Signed scope, data access agreement, baseline metrics"],
      ["3–5",   "CSDI integration deep dive",             "ALS + 3D Pedestrian Route Search wired, isochrone pipeline"],
      ["6–8",   "Diagnose + Expand archetypes end-to-end", "Storymap on full real BOCHK network, top-5 opportunity list"],
      ["9–10",  "Rationalise archetype, ATM cluster routing", "Replenishment-route templates, cannibalisation analysis"],
      ["11–12", "Polish, internal demo, public showcase", "HKSTP public demo + BOCHK case-study brief"],
    ];
    s.addTable(rows, {
      x: 0.5, y: 1.7, w: 9, colW: [1.2, 3.8, 4.0],
      fontFace: FONT_SANS, fontSize: 11.5, color: P.ink,
      border: { type: "solid", pt: 0.5, color: P.hair }, rowH: 0.5,
    });
    s.addText("Decision gate at end of week 5: do we have enough real-data evidence to commit to the full diagnose+expand storymap, or do we narrow scope.", {
      x: 0.5, y: 4.85, w: 9, h: 0.4,
      fontFace: FONT_SANS, fontSize: 12, italic: true, color: P.muted, margin: 0,
    });
  }

  // --- 11. Beyond banking ---------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Generalisation");
    title(s, "Same engine, different inputs");

    const verticals = [
      { t: "Retail chains",     b: "Convenience, F&B, pharmacy. Demand = people-driven + visit-driven blend." },
      { t: "Healthcare networks", b: "Clinics, day-care centres. Demand = visit-driven + demographic targeting." },
      { t: "Social services",  b: "HKCYS routing, elderly outreach. Catchment-fixed under slope constraints." },
      { t: "Real estate",      b: "Site selection, redevelopment scoring. Wealth and accessibility layers." },
    ];
    verticals.forEach((v, i) => {
      const x = 0.5 + (i % 2) * 4.6;
      const y = 1.75 + Math.floor(i / 2) * 1.7;
      s.addShape("rect", {
        x, y, w: 4.4, h: 1.5, fill: { color: "FFFFFF" },
        line: { color: P.hair, width: 0.75 }, shadow: shadow(),
      });
      s.addText(v.t, {
        x: x + 0.25, y: y + 0.2, w: 4.0, h: 0.4,
        fontFace: FONT_SERIF, fontSize: 17, bold: true, color: P.ink, margin: 0,
      });
      s.addText(v.b, {
        x: x + 0.25, y: y + 0.7, w: 4.0, h: 0.7,
        fontFace: FONT_SANS, fontSize: 12, color: P.muted, margin: 0,
      });
    });
  }

  // --- 12. Team + ask -------------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Closing");
    title(s, "The ask");

    s.addText([
      { text: "A 12-week HKSTP Spatial AI Sandbox slot ", options: { bold: true } },
      { text: "with BOCHK as the corporate partner.", options: { breakLine: true } },
      { text: " ", options: { breakLine: true } },
      { text: "We come with the engine built (FastAPI + Qwen agent + DuckDB-spatial + CSDI clients), the storymap UX shipped (MapLibre + scrollytelling), and the methodology committed (the four-question orchestrator). The sandbox is where it meets real BOCHK data, validates the recommendations against operational ground truth, and graduates to a productised offering.", options: {} },
    ], {
      x: 0.5, y: 1.7, w: 9, h: 2.5,
      fontFace: FONT_SANS, fontSize: 15, color: P.ink, paraSpaceAfter: 8, margin: 0,
    });
    // Three "what we need" cards
    const asks = [
      { t: "Sandbox slot",   b: "12-week engagement, HKSTP facilities." },
      { t: "Data access",    b: "BOCHK branch / ATM list, anonymised transaction footprint." },
      { t: "Success criteria", b: "Jointly defined at week 2; measured at week 12." },
    ];
    asks.forEach((a, i) => {
      const x = 0.5 + i * 3.05;
      s.addShape("rect", {
        x, y: 4.0, w: 2.9, h: 1.1, fill: { color: P.accent },
        line: { color: P.accent, width: 0 }, shadow: shadow(),
      });
      s.addText(a.t, {
        x: x + 0.2, y: 4.1, w: 2.6, h: 0.35,
        fontFace: FONT_SERIF, fontSize: 14, bold: true, color: "FFFFFF", margin: 0,
      });
      s.addText(a.b, {
        x: x + 0.2, y: 4.5, w: 2.6, h: 0.55,
        fontFace: FONT_SANS, fontSize: 11, color: "FFFFFF", margin: 0,
      });
    });
  }

  await pres.writeFile({ fileName: path.join(__dirname, "proposal.pptx") });
  console.log("Wrote proposal.pptx");
}

// =============================================================================
// BUSINESS PLAN DECK
// =============================================================================
async function buildBusinessPlan() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "Tochka — Business Plan";
  pres.author = "shults & partners";

  const N = 10;
  let idx = 0;

  // --- 1. Title -------------------------------------------------------------
  idx++;
  {
    const s = pres.addSlide();
    s.background = { color: P.paper };
    s.addText("TOCHKA · BUSINESS PLAN", {
      x: 0.6, y: 0.5, w: 8, h: 0.4,
      fontFace: FONT_SANS, fontSize: 12, bold: true, color: P.accent,
      charSpacing: 8, margin: 0,
    });
    s.addText("Location intelligence,\nas a service.", {
      x: 0.6, y: 1.5, w: 8.5, h: 2.2,
      fontFace: FONT_SERIF, fontSize: 44, bold: true, color: P.ink, margin: 0,
    });
    s.addText("Hong Kong banking beachhead → ASEAN financial services + retail networks.", {
      x: 0.6, y: 3.8, w: 8.5, h: 0.7,
      fontFace: FONT_SANS, fontSize: 16, color: P.muted, italic: true, margin: 0,
    });
    s.addText("shults & partners · submitted 26 May 2026", {
      x: 0.6, y: 4.9, w: 8.5, h: 0.4,
      fontFace: FONT_SANS, fontSize: 11, color: P.muted, margin: 0,
    });
  }

  // --- 2. Market ------------------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "The opportunity");
    title(s, "Hong Kong location intelligence is underserved");

    // Three numeric callouts
    const stats = [
      { n: "200+", l: "branches per major HK retail bank, each a spatial decision" },
      { n: "10K+", l: "physical retail outlets in HK with no spatial-intelligence layer" },
      { n: "50%",  l: "HKSTP assessment weight on CSDI — public data has matured" },
    ];
    stats.forEach((st, i) => {
      const x = 0.5 + i * 3.05;
      s.addText(st.n, {
        x, y: 1.8, w: 2.9, h: 1.1,
        fontFace: FONT_SERIF, fontSize: 60, bold: true, color: P.accent,
        align: "left", margin: 0,
      });
      s.addText(st.l, {
        x, y: 3.0, w: 2.9, h: 1.0,
        fontFace: FONT_SANS, fontSize: 13, color: P.ink, margin: 0,
      });
    });
    s.addText("Incumbents are heavy GIS suites (Esri) or unfocused dashboards. Nobody ships agent-driven location storymaps for HK banking.", {
      x: 0.5, y: 4.5, w: 9, h: 0.5,
      fontFace: FONT_SANS, fontSize: 13, italic: true, color: P.muted, margin: 0,
    });
  }

  // --- 3. Customer pain -----------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Customer pain");
    title(s, "Why the analyst can't answer this in a week");

    const pains = [
      { t: "Data is scattered",        b: "CSDI, OSM, GMaps, internal CRM, transaction logs — no unified workspace." },
      { t: "Tools require a specialist", b: "PostGIS, QGIS, ArcGIS skills sit outside the business team that needs the answer." },
      { t: "Methodology drifts",       b: "Every analyst picks demand model, isochrone definition, scoring rule differently." },
      { t: "Output is a dashboard",    b: "Executives want a recommendation, not a tile of charts to interpret." },
    ];
    pains.forEach((p, i) => {
      const x = 0.5 + (i % 2) * 4.6;
      const y = 1.75 + Math.floor(i / 2) * 1.65;
      s.addShape("rect", {
        x, y, w: 4.4, h: 1.45, fill: { color: "FFFFFF" },
        line: { color: P.hair, width: 0.75 }, shadow: shadow(),
      });
      s.addText(p.t, {
        x: x + 0.25, y: y + 0.18, w: 4.0, h: 0.4,
        fontFace: FONT_SERIF, fontSize: 16, bold: true, color: P.ink, margin: 0,
      });
      s.addText(p.b, {
        x: x + 0.25, y: y + 0.65, w: 4.0, h: 0.75,
        fontFace: FONT_SANS, fontSize: 12, color: P.muted, margin: 0,
      });
    });
  }

  // --- 4. Product -----------------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "The product");
    title(s, "An agent that picks the methodology and writes the answer");
    body(s,
      "Upload a CSV of locations. The orchestrator agent asks one clarifying question, sequences the right specialist tools (geocoding, isochrones, demand modelling, competitive landscape, anomaly detection), and produces a scroll-driven storymap with concrete recommendations. Five sections, end-to-end, in under three minutes.",
      { y: 1.75, h: 1.5, fontSize: 14.5 }
    );

    // Three accent boxes summarizing the value props
    const props = [
      { t: "Methodology, decided",  b: "Rule + LLM selection of demand model + analytical archetype." },
      { t: "Tools, sequenced",      b: "Deterministic Python tools; the agent picks order from the data." },
      { t: "Narrative, delivered",  b: "Qwen-written prose per section. Numbers stay verbatim." },
    ];
    props.forEach((pr, i) => {
      const x = 0.5 + i * 3.05;
      s.addShape("rect", {
        x, y: 3.4, w: 2.9, h: 1.7, fill: { color: P.accent },
        line: { color: P.accent, width: 0 }, shadow: shadow(),
      });
      s.addText(pr.t, {
        x: x + 0.25, y: 3.55, w: 2.5, h: 0.4,
        fontFace: FONT_SERIF, fontSize: 17, bold: true, color: "FFFFFF", margin: 0,
      });
      s.addText(pr.b, {
        x: x + 0.25, y: 4.0, w: 2.5, h: 1.0,
        fontFace: FONT_SANS, fontSize: 12, color: "FFFFFF", margin: 0,
      });
    });
  }

  // --- 5. Why us ------------------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Defensibility");
    title(s, "Why us, why now");

    const cols = [
      { kicker: "DOMAIN METHODOLOGY", body: "The four-question orchestrator isn't a model — it's a codified spatial-analyst playbook. New verticals require domain mapping, not retraining." },
      { kicker: "CSDI INTEGRATION DEPTH", body: "First-mover on the new HK public spatial stack — 3D Pedestrian Network, Population Distribution FSDT, iGeoCom — wired through DuckDB-spatial." },
      { kicker: "COMPOUNDING TOOL LIBRARY", body: "Every analyst engagement adds tools. Each tool generalises across the agent platform. Moat widens with usage." },
    ];
    cols.forEach((c, i) => {
      const x = 0.5 + i * 3.05;
      s.addText(c.kicker, {
        x, y: 1.85, w: 2.9, h: 0.3,
        fontFace: FONT_SANS, fontSize: 10, bold: true, color: P.accent, charSpacing: 3, margin: 0,
      });
      s.addText(c.body, {
        x, y: 2.2, w: 2.9, h: 2.6,
        fontFace: FONT_SANS, fontSize: 13.5, color: P.ink, margin: 0,
      });
    });
  }

  // --- 6. Go-to-market ------------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Go-to-market");
    title(s, "Beachhead, expansion, region");

    const rows = [
      ["Phase",    "Customer",                  "Motion",                          "Timeline"],
      ["Beachhead","BOCHK (HKSTP sandbox)",     "Reference engagement, joint case study", "Q2–Q3 2026"],
      ["Expand",   "Two more HK retail banks + 2 HK retail chains", "Warm intros via BOCHK + HKSTP", "Q4 2026 – Q1 2027"],
      ["Region",   "ASEAN financial services",  "Singapore + KL + Bangkok, partner-led",   "2027–2028"],
      ["Verticals","Healthcare, social services, real estate", "Same engine, new tools",          "Continuous"],
    ];
    s.addTable(rows, {
      x: 0.5, y: 1.7, w: 9, colW: [1.5, 3.3, 2.7, 1.5],
      fontFace: FONT_SANS, fontSize: 11.5, color: P.ink,
      border: { type: "solid", pt: 0.5, color: P.hair }, rowH: 0.55,
    });
  }

  // --- 7. Pricing -----------------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Commercials");
    title(s, "Hybrid: seat + usage");

    const tiers = [
      { t: "Sandbox",        p: "Included", b: "HKSTP 12-week engagement. No fee during the sandbox." },
      { t: "Team",           p: "HK$25k / mo", b: "Up to 5 analysts, 100 analyses / month, all archetypes." },
      { t: "Enterprise",     p: "From HK$120k / mo", b: "Unlimited seats, dedicated CSDI sync, private POI parser, SLA." },
    ];
    tiers.forEach((t, i) => {
      const x = 0.5 + i * 3.05;
      s.addShape("rect", {
        x, y: 1.75, w: 2.9, h: 3.0, fill: { color: "FFFFFF" },
        line: { color: P.hair, width: 0.75 }, shadow: shadow(),
      });
      s.addText(t.t.toUpperCase(), {
        x: x + 0.25, y: 1.95, w: 2.4, h: 0.3,
        fontFace: FONT_SANS, fontSize: 10, bold: true, color: P.accent, charSpacing: 3, margin: 0,
      });
      s.addText(t.p, {
        x: x + 0.25, y: 2.3, w: 2.4, h: 0.6,
        fontFace: FONT_SERIF, fontSize: 24, bold: true, color: P.ink, margin: 0,
      });
      s.addText(t.b, {
        x: x + 0.25, y: 3.0, w: 2.4, h: 1.6,
        fontFace: FONT_SANS, fontSize: 12, color: P.muted, margin: 0,
      });
    });
    s.addText("Pricing indicative. Anchor customers may negotiate equity-linked terms for the first 12 months.", {
      x: 0.5, y: 4.85, w: 9, h: 0.3,
      fontFace: FONT_SANS, fontSize: 11, italic: true, color: P.muted, margin: 0,
    });
  }

  // --- 8. Competitive landscape ---------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Competition");
    title(s, "Where we play, who else is there");

    const rows = [
      ["Competitor",           "What they sell",                  "Why we win"],
      ["Esri / ArcGIS",        "Enterprise GIS platform",         "Too heavy, requires GIS specialists, not agentic, not HK-native"],
      ["Aino (Finland)",       "Editorial location storymaps",    "No HK presence, no agent layer, no CSDI integration"],
      ["In-house GIS teams",   "Bespoke consulting",              "Slow, single-engagement, no compounding tool library"],
      ["Generalist LLM tools", "Chat-with-your-data wrappers",    "No spatial methodology, no tool determinism, no narrative shape"],
    ];
    s.addTable(rows, {
      x: 0.5, y: 1.7, w: 9, colW: [2.4, 3.0, 3.6],
      fontFace: FONT_SANS, fontSize: 11.5, color: P.ink,
      border: { type: "solid", pt: 0.5, color: P.hair }, rowH: 0.55,
    });
  }

  // --- 9. Roadmap -----------------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Twelve-month view");
    title(s, "Roadmap");

    const rows = [
      ["Period",       "Theme",                         "Headline deliverables"],
      ["Q3 2026",      "Sandbox completion (HKSTP)",    "Full BOCHK storymap, public showcase, case-study brief"],
      ["Q4 2026",      "Productisation",                "Multi-tenant SaaS, customer-managed POI parser, billing"],
      ["Q1 2027",      "HK expansion",                  "2 retail banks + 2 retail chains live"],
      ["Q2–Q3 2027",   "ASEAN entry",                   "Singapore via finance partner, Bangkok via retail partner"],
      ["Q4 2027",      "Vertical expansion",            "Healthcare + social services tool packs"],
    ];
    s.addTable(rows, {
      x: 0.5, y: 1.7, w: 9, colW: [1.6, 2.8, 4.6],
      fontFace: FONT_SANS, fontSize: 11.5, color: P.ink,
      border: { type: "solid", pt: 0.5, color: P.hair }, rowH: 0.5,
    });
  }

  // --- 10. The ask ----------------------------------------------------------
  idx++;
  {
    const s = baseSlide(pres, idx, N);
    eyebrow(s, "Closing");
    title(s, "What we need from HKSTP");

    const asks = [
      { t: "Sandbox slot + facilities", b: "12-week engagement, HKSTP studio access, BOCHK introduction confirmed." },
      { t: "Seed-equivalent support",   b: "Operating runway during the sandbox; founding team off the runway clock." },
      { t: "Anchor customer intros",    b: "Two further HK enterprises by end of sandbox week 12." },
      { t: "Public showcase",           b: "Demo slot at HKSTP showcase event, joint PR with BOCHK." },
    ];
    asks.forEach((a, i) => {
      const x = 0.5 + (i % 2) * 4.6;
      const y = 1.75 + Math.floor(i / 2) * 1.55;
      s.addShape("rect", {
        x, y, w: 4.4, h: 1.35, fill: { color: P.accent },
        line: { color: P.accent, width: 0 }, shadow: shadow(),
      });
      s.addText(a.t, {
        x: x + 0.25, y: y + 0.18, w: 4.0, h: 0.4,
        fontFace: FONT_SERIF, fontSize: 16, bold: true, color: "FFFFFF", margin: 0,
      });
      s.addText(a.b, {
        x: x + 0.25, y: y + 0.6, w: 4.0, h: 0.7,
        fontFace: FONT_SANS, fontSize: 12, color: "FFFFFF", margin: 0,
      });
    });
    s.addText("Tochka. Agent-driven location intelligence for Hong Kong, then the region.", {
      x: 0.5, y: 4.95, w: 9, h: 0.3,
      fontFace: FONT_SERIF, fontSize: 13, italic: true, color: P.ink, align: "center", margin: 0,
    });
  }

  await pres.writeFile({ fileName: path.join(__dirname, "business_plan.pptx") });
  console.log("Wrote business_plan.pptx");
}

// --- main ---
await buildProposal();
await buildBusinessPlan();
