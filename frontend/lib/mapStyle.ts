/**
 * Basemap style URL.
 *
 * Order of preference:
 *   1. NEXT_PUBLIC_BASEMAP_STYLE        — explicit override (any URL).
 *   2. NEXT_PUBLIC_MAPBOX_STYLE_URL +
 *      NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN  — convert mapbox://styles/... to
 *                                        a public Style API URL with the
 *                                        token appended.
 *   3. Carto Positron                   — robust, always-available default.
 *
 * CSDI's vector style URL still 404s; we explicitly reject any URL that
 * contains that dead host so a stale `.env.local` can't poison the map.
 */

const DEFAULT_BASEMAP =
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

function isUsable(url: string | undefined | null): url is string {
  if (!url) return false;
  if (url.includes("mapapi.geodata.gov.hk")) return false;
  return true;
}

/** Convert a `mapbox://styles/<user>/<style>` URI into a Style API URL.
 *  Returns null if the input is not a mapbox:// style or if no token is set. */
function mapboxToHttp(styleUri: string | undefined | null, token: string | undefined | null): string | null {
  if (!styleUri || !token) return null;
  const m = styleUri.match(/^mapbox:\/\/styles\/([^/]+)\/([^/?#]+)/);
  if (!m) return null;
  const [, user, styleId] = m;
  return `https://api.mapbox.com/styles/v1/${user}/${styleId}?access_token=${encodeURIComponent(token)}`;
}

export function csdiStyleUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_BASEMAP_STYLE;
  if (isUsable(explicit)) return explicit;

  // Mapbox: NEXT_PUBLIC_MAPBOX_STYLE_URL must be a `mapbox://styles/...` URI.
  const mb = mapboxToHttp(
    process.env.NEXT_PUBLIC_MAPBOX_STYLE_URL,
    process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN,
  );
  if (mb) return mb;

  return DEFAULT_BASEMAP;
}
