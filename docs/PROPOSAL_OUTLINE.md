# HKSTP proposal — 10-beat narrative

Two decks, 10–20 pages each, due **2026-05-26 noon**, ≤25 MB:
1. **Proposal** — what we will build during the sandbox.
2. **Business plan** — how it becomes a product.

This file outlines the proposal deck. Business plan outline is at the bottom.

---

## Proposal deck — 10 beats

### 1. Title (1 page)
"Tochka — agent-driven location intelligence for Hong Kong banking." Logos, team, partner (BOCHK), date.

### 2. Why now (1 page)
Banking networks are sized for a population that has shifted. Public sector spatial data (CSDI) has reached the depth and freshness needed for agentic analysis: 3D Pedestrian Network, Population Distribution (Mar 2025), iGeoCom. LLMs can now sequence specialist spatial tools reliably.

### 3. BOCHK's problem in three pictures (2 pages)
- **Picture A** — branch / ATM coverage map overlaid on 2025 population. Visible gaps and over-coverage.
- **Picture B** — peak-hour queue density vs branch capacity. Same staffing, very different load.
- **Picture C** — POS transaction hotspots vs premium-POI density. Wealth segmentation by neighbourhood.

### 4. The product in one screen (1 page)
Screenshot of the storymap. Five sections previewed. Caption: "Upload a CSV. The agent decides the methodology. You read the storymap."

### 5. How the agent thinks (1 page)
The four orchestrator questions, on one diagram. Network → demand model → analytical archetype → data plan. Tools as cards underneath.

### 6. CSDI inside (2 pages)
Map each storymap section to the CSDI APIs and datasets it consumes. Highlight: 3D Pedestrian Network for true walk catchments, Population Distribution FSDT for demand surfaces, iGeoCom + Streetscape for narrative depth. This is the page that wins the 50% CSDI weighting.

### 7. Sandbox plan — 12 weeks (2 pages)
| Weeks | Milestone |
|---|---|
| 1–2 | BOCHK data intake, methodology lock-in |
| 3–5 | CSDI integration deep dive, isochrone pipeline on 3D Pedestrian Network |
| 6–8 | Diagnose + Expand archetypes end-to-end on real BOCHK data |
| 9–10 | Rationalise archetype, ATM cluster routing, POS affinity layer |
| 11–12 | Storymap polish, internal demo to BOCHK, public showcase |

### 8. Beyond banking (1 page)
Same engine, different inputs: retail chains, F&B, healthcare networks, social services (HKCYS), real estate. Three customer logos to target post-sandbox.

### 9. The team (1 page)
Founder, advisors, BOCHK liaison. Hackathon track record (SiteSense). Why a small team can ship this in 12 weeks.

### 10. Ask (1 page)
Sandbox slot, BOCHK data access scope, success criteria. Single line CTA.

---

## Business plan deck — outline

1. Title.
2. Market — HK location-intelligence TAM, banking adjacencies, public-sector beachhead.
3. Customer pain — banking, retail, healthcare, social services. Quantified.
4. Product — same screenshot, with a "customer view" emphasis.
5. Why us — agents + CSDI depth = compounding moat as we add tool coverage.
6. Go-to-market — beachhead with BOCHK, expand to two HK retail chains, then ASEAN finance.
7. Pricing — seat + usage hybrid, sandbox is free during the 12 weeks.
8. Competitive landscape — Aino (no HK presence), Esri (heavy, not agentic), in-house GIS teams (slow).
9. Roadmap — 12 weeks sandbox, 6 months product, 12 months ASEAN.
10. The ask — seed-equivalent support during sandbox, partnership terms, intro to two more anchor customers.

## Production notes

- Build slides in Keynote or Google Slides → export as PDF and PPTX, keep file under 25 MB by compressing screenshots to 1600 px wide JPG-q80.
- Maintain a single shared figures folder: `docs/figures/` (to be added). Each figure has a number and one-line caption.
- Use the cartography palette in `frontend/lib/cartography.ts` for any map figures so the proposal matches the demo.
