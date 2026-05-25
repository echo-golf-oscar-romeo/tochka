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
    // `mapbox://styles/<u>/<s>` → /styles/v1/<u>/<s>
    const path = tail.slice("styles/".length);
    httpUrl = `https://api.mapbox.com/styles/v1/${path}`;
  } else if (tail.startsWith("sprites/")) {
    // MapLibre's request manager appends format+extension to the sprite URL
    // BEFORE calling transformRequest, so we receive shapes like:
    //   mapbox://sprites/<u>/<s>.json
    //   mapbox://sprites/<u>/<s>@2x.png
    //   mapbox://sprites/<u>/<s>.png
    // We have to insert "/sprite" between the style id and the extension —
    // not at the end — otherwise we end up with the extension stuck inside
    // the style id and the request 404s.
    const m = tail.match(/^sprites\/([^/]+)\/([^.@]+)(.*)$/);
    if (m) {
      const [, user, styleId, suffix] = m;
      httpUrl = `https://api.mapbox.com/styles/v1/${user}/${styleId}/sprite${suffix}`;
    } else {
      // Bare sprite URL (no extension yet).
      const path = tail.slice("sprites/".length);
      httpUrl = `https://api.mapbox.com/styles/v1/${path}/sprite`;
    }
  } else if (tail.startsWith("fonts/")) {
    // mapbox://fonts/<u>/{stack}/{range}.pbf → /fonts/v1/<u>/{stack}/{range}.pbf
    // The fontstack + range + extension are all already in the path; a
    // plain prefix swap is correct.
    const path = tail.slice("fonts/".length);
    httpUrl = `https://api.mapbox.com/fonts/v1/${path}`;
  } else {
    // Vector source or tile under /v4.
    //   Source TileJSON: `mapbox://mapbox.mapbox-streets-v8`
    //                  → /v4/mapbox.mapbox-streets-v8.json?secure
    //   Combined:        `mapbox://mapbox.streets-v8,mapbox.terrain-v2`
    //                  → /v4/mapbox.streets-v8,mapbox.terrain-v2.json?secure
    //   Tile:            `mapbox://<tileset>/<z>/<x>/<y>.<ext>`
    //                  → /v4/<tileset>/<z>/<x>/<y>.<ext>
    // We detect tile shape by the embedded {z}/{x}/{y} segment so we don't
    // rely on resourceType (MapLibre doesn't always set it for our hook).
    const looksLikeTile = /\/\d+\/\d+\/\d+\./.test(tail);
    if (looksLikeTile) {
      httpUrl = `https://api.mapbox.com/v4/${tail}`;
    } else {
      httpUrl = `https://api.mapbox.com/v4/${tail}.json?secure`;
    }
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
