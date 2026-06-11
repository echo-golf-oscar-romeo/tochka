"""Overlay multi-factor analysis: which spatial features drive performance.

The "optimise the metric" workflow — given locations with a target variable
(e.g. actual_volume / footfall / revenue) and their spatial-context
embeddings, fit a linear model to learn which contextual factors most
explain success, then score candidate sites by predicted potential.

Uses scikit-learn LinearRegression on z-scored features so the coefficients
are directly comparable (standardised betas = feature importance with sign).
Honest about small-n: reports R² and sample size; this is directional
guidance, not a published econometric model.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.tools.similarity import build_feature_vectors

log = logging.getLogger(__name__)


def fit_drivers(locations: list[dict], target_key: str = "actual_volume") -> dict[str, Any]:
    """Fit target ~ spatial features; return standardised coefficients
    (importance + direction), R², and per-location residuals (over/under
    performance vs. what context predicts)."""
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler

    have = [loc for loc in locations if loc.get(target_key) not in (None, "")]
    if len(have) < 4:
        return {
            "method": "regression",
            "error": "insufficient_data",
            "note": f"Need at least 4 locations with '{target_key}'; got {len(have)}.",
        }
    X, names = build_feature_vectors(have)
    y = np.array([float(loc[target_key]) for loc in have], dtype=float)

    scaler = StandardScaler()
    Xz = scaler.fit_transform(X)
    model = LinearRegression().fit(Xz, y)
    r2 = float(model.score(Xz, y))
    pred = model.predict(Xz)
    resid = y - pred

    drivers = sorted(
        (
            {"feature": names[i], "beta": round(float(model.coef_[i]), 2)}
            for i in range(len(names))
        ),
        key=lambda d: abs(d["beta"]),
        reverse=True,
    )
    # Honesty about small samples: with fewer rows than features the fit is
    # underdetermined (R² near 1 is overfit, not signal).
    n_feat = len(names)
    if len(have) <= n_feat:
        reliability = "low"
        reliability_note = (
            f"Only {len(have)} locations for {n_feat} features — the model is "
            "underdetermined; treat the drivers as directional, not definitive."
        )
    elif len(have) < 2 * n_feat:
        reliability = "moderate"
        reliability_note = f"{len(have)} locations for {n_feat} features — limited sample."
    else:
        reliability = "good"
        reliability_note = ""
    locs_out = []
    for loc, yi, pi, ri in zip(have, y, pred, resid, strict=False):
        q = dict(loc)
        q["predicted"] = round(float(pi), 1)
        q["residual"] = round(float(ri), 1)
        q["performance"] = "over" if ri > 0 else "under"
        locs_out.append(q)
    return {
        "method": "regression",
        "target": target_key,
        "r2": round(r2, 3),
        "n": len(have),
        "reliability": reliability,
        "reliability_note": reliability_note,
        "drivers": drivers,
        "locations": locs_out,
    }


def predict_potential(trained_locations: list[dict], candidates: list[dict],
                      target_key: str = "actual_volume") -> dict[str, Any]:
    """Fit on `trained_locations`, predict the target for `candidates`."""
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler

    have = [loc for loc in trained_locations if loc.get(target_key) not in (None, "")]
    if len(have) < 4 or not candidates:
        return {"method": "predict_potential", "error": "insufficient_data", "results": []}
    Xtr, names = build_feature_vectors(have)
    ytr = np.array([float(loc[target_key]) for loc in have], dtype=float)
    scaler = StandardScaler().fit(Xtr)
    model = LinearRegression().fit(scaler.transform(Xtr), ytr)

    Xc, _ = build_feature_vectors(candidates)
    preds = model.predict(scaler.transform(Xc))
    results = []
    for c, pi in zip(candidates, preds, strict=False):
        q = dict(c)
        q["predicted_potential"] = round(float(pi), 1)
        results.append(q)
    results.sort(key=lambda d: d["predicted_potential"], reverse=True)
    return {"method": "predict_potential", "target": target_key, "results": results}
