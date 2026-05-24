import SectionPanel from "./_SectionPanel";
import type { StorymapSection } from "@/lib/storymap";

export default function WhatsWorking({ section }: { section: StorymapSection }) {
  return <SectionPanel section={section} accent="warn" />;
}
