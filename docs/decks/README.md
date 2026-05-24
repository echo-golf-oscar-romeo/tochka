# HKSTP decks

Two PowerPoint decks for the HKSTP Spatial AI Sandbox PoC Challenge submission (due 2026-05-26 noon).

| File | Slides | Purpose |
|---|---|---|
| `proposal.pptx` | 12 | What we will build during the 12-week sandbox |
| `business_plan.pptx` | 10 | How Tochka becomes a product post-sandbox |

## What's real vs illustrative

All quantitative claims about BOCHK and HK banking inside these decks are **illustrative — synthetic data**, marked as such in figure captions and slide footers. The proposal is honest that BOCHK ground-truth analysis is the *output* of the sandbox engagement, not the input.

Real components referenced in the decks (all already implemented in this repo):
- The FastAPI + Qwen-Agent orchestrator with the four-question methodology — `backend/app/orchestrator/`.
- The deterministic tool library across geocoding / reachability / demand / competitors / spatial / modelling — `backend/app/tools/`.
- The MapLibre + CSDI-Vector storymap UI with scroll-driven Mapbox-Storytelling-pattern chapters — `frontend/`.
- DashScope/Qwen integration for clarify + per-section narrative — `backend/app/orchestrator/llm.py`.

## Regenerate

```bash
# Figures
pip install matplotlib numpy
python docs/figures_gen.py

# Decks
cd docs/decks
npm install               # one-time; pins pptxgenjs locally
node build.mjs
```

Outputs land next to `build.mjs`. Open the `.pptx` files in PowerPoint or Keynote.

## Editing path

These decks are a *starting point*. Expected workflow before submission:
1. Open `proposal.pptx` in PowerPoint.
2. Replace any of the three matplotlib figures with real screenshots from the running app once CSDI data is wired in — keep the `Illustrative / synthetic` footer until the screenshot is genuinely from BOCHK data.
3. Tighten the team slide once names and roles are confirmed.
4. Export as PDF (HKSTP accepts both PPTX and PDF), confirm < 25 MB.

## Files

- `build.mjs` — pptxgenjs script that builds both decks
- `package.json` / `package-lock.json` — pins pptxgenjs version locally so the build is reproducible
- `proposal.pptx`, `business_plan.pptx` — generated outputs (committed for reviewer convenience)
- `../figures_gen.py` — matplotlib figure generator
- `../figures/*.png` — generated PNG figures embedded into proposal slides 4–6
