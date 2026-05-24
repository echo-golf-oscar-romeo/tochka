/**
 * Aino-inspired cartography palette and layer defaults.
 *
 * Cartographic principle: quiet basemap, two strong accents for data, generous
 * whitespace in chapter text. The user-network and isochrones share a hue to
 * read as one entity; competitors use a contrasting warm; anomalies use red.
 */

export const palette = {
  paper: "#f6f4ef",
  ink: "#1a1a1a",
  muted: "#6b6760",
  userNetwork: "#0f5ea8",
  competitor: "#e07a5f",
  isochrone: "#0f5ea8",
  hexLow: "#f6f4ef",
  hexHigh: "#1a1a1a",
  anomalyUnder: "#c44536",
  anomalyOver: "#3a7d44",
} as const;

export const defaultPaint = {
  userNetwork: {
    "circle-color": palette.userNetwork,
    "circle-radius": 6,
    "circle-stroke-color": "#fff",
    "circle-stroke-width": 1,
  },
  isochrone: {
    "fill-color": palette.isochrone,
    "fill-opacity": 0.15,
    "fill-outline-color": palette.isochrone,
  },
  competitor: {
    "circle-color": palette.competitor,
    "circle-radius": 4,
    "circle-opacity": 0.85,
  },
  anomalyUnder: {
    "circle-color": palette.anomalyUnder,
    "circle-radius": 9,
    "circle-stroke-color": "#fff",
    "circle-stroke-width": 2,
  },
} as const;
