import SectionPanel from "./_SectionPanel";
import type { StorymapSection } from "@/lib/storymap";

interface Props { section: StorymapSection; onFitToSection?: () => void }

export default function NetworkAtGlance({ section, onFitToSection }: Props) {
  return <SectionPanel section={section} accent="accent" onFitToSection={onFitToSection} />;
}
