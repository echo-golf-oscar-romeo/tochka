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


/** Read the public Mapbox access token. Used by the MapCanvas transform-
 *  request hook so MapLibre can resolve `mapbox://…` URIs found inside the
 *  fetched style JSON (vector sources, sprites, glyphs). Without this, a
 *  Mapbox style loads but the map renders blank because MapLibre can't fetch
 *  the actual tiles. */
export function mapboxToken(): string | null {
  const t = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN;
  return t && t.length > 0 ? t : null;
}


/** Convert any `mapbox://` URL to its public Mapbox API equivalent.
 *  Covers the four shapes the Style API embeds:
 *
 *    mapbox://styles/<user>/<style>           → /styles/v1/<user>/<style>
 *    mapbox://sprites/<user>/<style>          → /styles/v1/<user>/<style>/sprite
 *    mapbox://fonts/<user>/{fontstack}/{range} → /fonts/v1/<user>/{fontstack}/{range}
 *    mapbox://<tileset[,tileset…]>            → /v4/<tilesets>/{z}/{x}/{y}.vector.pbf
 *
 *  Anything else falls through unchanged. The token is appended as a query
 *  parameter (merged into any existing `?…`). */
export function rewriteMapboxUrl(url: string, token: string, resourceType?: string): string {
  if (!url.startsWith("mapbox://")) return url;
  const tail = url.slice("mapbox://".length);
  let httpUrl: string;

  if (tail.startsWith("styles/")) {
    // sprites for a style come back as `mapbox://sprites/<u>/<s>` in style
    // JSON, but MapLibre also sometimes asks for the style itself.
    const path = tail.slice("styles/".length);
    httpUrl = `https://api.mapbox.com/styles/v1/${path}`;
  } else if (tail.startsWith("sprites/")) {
    const path = tail.slice("sprites/".length);
    // MapLibre passes the resourceType so we know whether to ask for
    // /sprite.json or /sprite.png; we strip any existing extension and let
    // MapLibre's request flow re-append it via the URL params it sends.
    httpUrl = `https://api.mapbox.com/styles/v1/${path}/sprite`;
  } else if (tail.startsWith("fonts/")) {
    const path = tail.slice("fonts/".length);
    httpUrl = `https://api.mapbox.com/fonts/v1/${path}`;
  } else if (resourceType === "Source" || resourceType === "Tile") {
    // Vector source: `mapbox://mapbox.mapbox-streets-v8,mapbox.terrain-v2`
    // Tile pattern includes {z}/{x}/{y}; MapLibre fetches the source JSON
    // first (resourceType "Source"), then individual tiles (resourceType
    // "Tile"). The latter already include the {z}/{x}/{y} path tail.
    const slashIdx = tail.indexOf("/");
    if (slashIdx === -1) {
      // Source request — return the source JSON descriptor.
      httpUrl = `https://api.mapbox.com/v4/${tail}.json?secure`;
    } else {
      // Tile request: `<tileset>/<z>/<x>/<y>.<ext>` already encoded.
      httpUrl = `https://api.mapbox.com/v4/${tail}`;
    }
  } else {
    // Unknown shape — best-effort: drop the prefix and serve it under /v4.
    httpUrl = `https://api.mapbox.com/v4/${tail}`;
  }

  const sep = httpUrl.includes("?") ? "&" : "?";
  return `${httpUrl}${sep}access_token=${encodeURIComponent(token)}`;
}


/** Factory for a MapLibre `transformRequest` that rewrites Mapbox URIs.
 *  Returns null when no token is configured (caller can pass `undefined`
 *  straight through to MapLibre — non-Mapbox basemaps don't need this). */
export function makeMapboxTransformRequest(token: string | null) {
  if (!token) return undefined;
  return (url: string, resourceType?: string) => {
    if (url.startsWith("mapbox://")) {
      return { url: rewriteMapboxUrl(url, token, resourceType) };
    }
    return { url };
  };
}
