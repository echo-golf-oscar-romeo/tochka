import SectionPanel from "./_SectionPanel";
import type { StorymapSection } from "@/lib/storymap";

export default function WhoYouReach({ section }: { section: StorymapSection }) {
  return <SectionPanel section={section} accent="accent" />;
}
