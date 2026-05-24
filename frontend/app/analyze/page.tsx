// The `/analyze` route is superseded by the map-first workspace at `/`.
// Redirect any stale links so people don't land on an empty page.
import { redirect } from "next/navigation";

export default function AnalyzePage() {
  redirect("/");
}
