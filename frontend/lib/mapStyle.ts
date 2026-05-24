/**
 * Basemap style URL.
 *
 * Defaults to Carto Positron — a clean light vector basemap that reads
 * well under data. CSDI's vector style URL still 404s as of writing;
 * we explicitly reject any URL that contains the dead host so a stale
 * `.env.local` from earlier in development can't poison the map.
 *
 * To override: set `NEXT_PUBLIC_BASEMAP_STYLE`.
 */

const DEFAULT_BASEMAP =
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

function isUsable(url: string | undefined | null): url is string {
  if (!url) return false;
  // The CSDI vector style URL returns 404 + CORS-blocked; ignore it even
  // if a developer left it in .env from an older example.
  if (url.includes("mapapi.geodata.gov.hk")) return false;
  return true;
}

export function csdiStyleUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_BASEMAP_STYLE;
  if (isUsable(explicit)) return explicit;
  return DEFAULT_BASEMAP;
}
