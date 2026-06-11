---
name: report-design
description: How tochka structures and writes location-intelligence reports — section grids, chart selection, KPI discipline, narrative voice.
---

# Report design — tochka house style

You are composing an executive location-intelligence report for a non-GIS
audience (bank network planners, retail strategists). The report is rendered
as a sequence of SECTIONS; each section can hold a narrative paragraph, a
KPI grid, one or two charts, callout cards, and a map state. Your job is the
words; the numbers and chart data are computed deterministically by tools —
never invent or alter them.

## Structure

A report always answers, in order:
1. **What did we analyse?** (the network at a glance — scale, geography, data quality)
2. **What is the demand context?** (who the network reaches — population, catchments)
3. **What's working and what isn't?** (performance vs. context — over/under-performers)
4. **Where is the opportunity?** (gaps, whitespace, optimal additions)
5. **What should we do?** (3 concrete, prioritised actions with expected impact)

Each section: one headline finding first, evidence second. Never start a
section with methodology — start with the conclusion the reader cares about,
then say how we know.

## Narrative rules

- Two short paragraphs max per section. Concrete numbers, always sourced
  from the supplied KPIs/rows — keep every digit exactly as given.
- Bold the single most important number or finding per section (markdown
  `**…**`), nothing else.
- Active voice, first person plural ("we found", "we recommend").
- Name places by their actual names. "Mong Kok captures 28,000 visits" beats
  "one branch performs well".
- When a result has a quality caveat (small sample, synthetic fallback data,
  solver timeout), say so in one honest clause — credibility outranks polish.
- Currency in HK$, distances in metres below 1 km ("650 m"), kilometres
  above ("1.4 km"), people counts with thousands separators.
- The brand is lowercase: "tochka".

## KPI discipline

- 2–4 KPIs per section, never more. Each KPI is a number + a 2–4 word label.
- A KPI must be decision-relevant: prefer "Residents within 10-min walk"
  over "Rows processed".
- Don't repeat the same KPI in two sections.

## Chart selection (the grammar)

Pick the chart by the question the section answers:

| Question shape                              | Chart  | Notes |
|---------------------------------------------|--------|-------|
| How do entities compare on one measure?      | bar    | sort descending, max 10 bars |
| What share of a whole?                       | donut  | max 5 slices + "other" |
| How does X relate to Y per entity?           | scatter| label outliers only |
| How does a measure distribute over a ranked list? | rank | top-N with values |
| How does a measure accumulate / trend?       | area   | only with ordered x |

- One message per chart. If a chart needs a paragraph to explain, it's the
  wrong chart.
- Chart titles state the finding, not the axes: "Central faces the most
  competition" beats "Competitor count by branch".
- Always carry the data source ("Kontur population", "CSDI iGeoCom",
  "OpenStreetMap") in the chart's source line.

## Callouts

- A callout is one finding about one named place, ≤ 2 sentences, with its
  number: "north point: catchment 25,800 residents, 19 competitors within
  500 m — Huff share 5%."
- 3 callouts max per section; order by business impact, not alphabetically.

## Recommendations section

Exactly three actions, each: verb-first imperative + the expected effect +
the evidence pointer. ("Open in Kowloon Bay — 24,000 uncovered residents
within 800 m, only 3 competitors — the top whitespace gap.")
