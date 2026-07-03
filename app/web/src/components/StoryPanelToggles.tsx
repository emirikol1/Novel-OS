import { useLayoutPrefs } from "../context/LayoutPrefs";
import PanelToggle from "./PanelToggle";

export default function StoryPanelToggles({ className = "" }: { className?: string }) {
  const {
    showLibrary,
    toggleLibrary,
    showBinder,
    toggleBinder,
    showInspector,
    toggleInspector,
  } = useLayoutPrefs();

  return (
    <div className={`flex h-7 shrink-0 overflow-hidden rounded-lg border border-paper-line ${className}`}>
      <PanelToggle on={showLibrary} onClick={toggleLibrary} label="Library" tipId="chapter.toggleLibrary" />
      <PanelToggle on={showBinder} onClick={toggleBinder} label="Binder" border tipId="chapter.toggleBinder" />
      <PanelToggle
        on={showInspector}
        onClick={toggleInspector}
        label="Notes"
        border
        tipId="chapter.toggleInspector"
      />
    </div>
  );
}
