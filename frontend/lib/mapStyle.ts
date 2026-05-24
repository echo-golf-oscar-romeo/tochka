/**
 * Basemap style URL.
 *
 * Default: Carto Positron — a light, subtle vector style that reads well
 * under data layers (Aino-style). Cross-origin enabled, no auth required.
 *
 * The original CSDI Vector Map URL
 * (https://mapapi.geodata.gov.hk/gs/api/v1.0.0/styleSheet/vector) currently
 * returns 404 — CSDI changed their API surface. When CSDI republishes a
 * working vector style URL, point NEXT_PUBLIC_BASEMAP_STYLE at it via
 * `.env.local` and the app will pick it up without code changes.
 *
 * For backward compatibility we still read the older
 * NEXT_PUBLIC_CSDI_VECTOR_STYLE name as a secondary override.
 */
export function csdiStyleUrl(): string {
  return (
    process.env.NEXT_PUBLIC_BASEMAP_STYLE ??
    process.env.NEXT_PUBLIC_CSDI_VECTOR_STYLE ??
    "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
  );
}
