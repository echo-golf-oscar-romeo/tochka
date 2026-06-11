"""Spatial distance-decay kernels.

The weight a location of demand assigns to a facility falls off with
distance. These kernels turn a distance (metres) into an accessibility
weight in [0, 1], and feed gravity / Huff share models.

  exponential:  w = exp(-d / scale)          — steady decay, scale = e-folding distance
  gaussian:     w = exp(-0.5 (d/scale)^2)     — flat near 0, sharp cutoff (walkability)
  power:        w = (1 + d)^(-beta)           — heavy tail, classic gravity
  linear:       w = max(0, 1 - d/scale)       — hard cutoff at `scale`

`scale` defaults to 800 m (≈10-min walk). Vectorised over numpy arrays.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

Kernel = Literal["exponential", "gaussian", "power", "linear"]


def decay_weight(distance_m, kernel: Kernel = "exponential",
                 scale: float = 800.0, beta: float = 1.5):
    """Distance(s) → accessibility weight(s) in [0, 1]. Accepts scalar or array."""
    d = np.asarray(distance_m, dtype=float)
    if kernel == "gaussian":
        w = np.exp(-0.5 * (d / scale) ** 2)
    elif kernel == "power":
        w = np.power(1.0 + d, -beta)
    elif kernel == "linear":
        w = np.clip(1.0 - d / scale, 0.0, 1.0)
    else:  # exponential (default)
        w = np.exp(-d / scale)
    return float(w) if np.isscalar(distance_m) else w


def gravity_attractiveness(facility_size, distance_m, kernel: Kernel = "exponential",
                           scale: float = 800.0, beta: float = 1.5):
    """Huff numerator: attractiveness = size * decay(distance).

    `facility_size` is a pull mass (capacity, floor area, # services).
    Returns the same shape as the broadcast of inputs."""
    size = np.asarray(facility_size, dtype=float)
    return size * decay_weight(distance_m, kernel=kernel, scale=scale, beta=beta)


def huff_shares(facility_sizes, distance_matrix, kernel: Kernel = "exponential",
                scale: float = 800.0, beta: float = 1.5) -> np.ndarray:
    """Huff probability matrix P[i, j] = share of demand point i captured by
    facility j. distance_matrix is (n_demand, n_facilities) in metres.
    Rows sum to 1 (or 0 where no facility is reachable)."""
    sizes = np.asarray(facility_sizes, dtype=float)[None, :]
    attr = sizes * decay_weight(distance_matrix, kernel=kernel, scale=scale, beta=beta)
    row = attr.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        shares = np.where(row > 0, attr / row, 0.0)
    return shares
