/**
 * CSDI Vector Map basemap.
 *
 * The CSDI portal publishes a public style URL that MapLibre can consume directly.
 * Keep the URL configurable via env so we can swap if CSDI updates the path.
 */
export function csdiStyleUrl(): string {
  return (
    process.env.NEXT_PUBLIC_CSDI_VECTOR_STYLE ??
    "https://mapapi.geodata.gov.hk/gs/api/v1.0.0/styleSheet/vector"
  );
}
