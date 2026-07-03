import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import {
  INSPECTOR_WIDTH_DEFAULT,
  INSPECTOR_WIDTH_MAX,
  INSPECTOR_WIDTH_MIN,
  clampPanelWidth,
} from "../lib/chapterStudioLayout";

const STORAGE_KEY = "novel-os-layout-prefs";
const LEGACY_LIBRARY_KEY = "novel-os-show-library";

type StoredLayoutPrefs = {
  showLibrary: boolean;
  showBinder: boolean;
  showInspector: boolean;
  inspectorWidth: number;
};

type LayoutPrefs = StoredLayoutPrefs & {
  setShowLibrary: (v: boolean) => void;
  toggleLibrary: () => void;
  setShowBinder: (v: boolean) => void;
  toggleBinder: () => void;
  setShowInspector: (v: boolean) => void;
  toggleInspector: () => void;
  setInspectorWidth: (v: number) => void;
};

const DEFAULTS: StoredLayoutPrefs = {
  showLibrary: true,
  showBinder: true,
  showInspector: true,
  inspectorWidth: INSPECTOR_WIDTH_DEFAULT,
};

function normalizeStored(parsed: Partial<StoredLayoutPrefs>): StoredLayoutPrefs {
  return {
    showLibrary: parsed.showLibrary ?? DEFAULTS.showLibrary,
    showBinder: parsed.showBinder ?? DEFAULTS.showBinder,
    showInspector: parsed.showInspector ?? DEFAULTS.showInspector,
    inspectorWidth: clampPanelWidth(
      parsed.inspectorWidth ?? DEFAULTS.inspectorWidth,
      INSPECTOR_WIDTH_MIN,
      INSPECTOR_WIDTH_MAX,
      INSPECTOR_WIDTH_DEFAULT,
    ),
  };
}

const LayoutPrefsContext = createContext<LayoutPrefs | null>(null);

function readStored(): StoredLayoutPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<StoredLayoutPrefs>;
      return normalizeStored({ ...DEFAULTS, ...parsed });
    }
    const legacy = localStorage.getItem(LEGACY_LIBRARY_KEY);
    if (legacy === "0" || legacy === "false") {
      return normalizeStored({ ...DEFAULTS, showLibrary: false });
    }
  } catch {
    /* ignore */
  }
  return DEFAULTS;
}

export function LayoutPrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState(readStored);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch {
      /* ignore */
    }
  }, [prefs]);

  const setShowLibrary = useCallback((v: boolean) => {
    setPrefs((p) => (p.showLibrary === v ? p : { ...p, showLibrary: v }));
  }, []);
  const toggleLibrary = useCallback(() => {
    setPrefs((p) => ({ ...p, showLibrary: !p.showLibrary }));
  }, []);

  const setShowBinder = useCallback((v: boolean) => {
    setPrefs((p) => (p.showBinder === v ? p : { ...p, showBinder: v }));
  }, []);
  const toggleBinder = useCallback(() => {
    setPrefs((p) => ({ ...p, showBinder: !p.showBinder }));
  }, []);

  const setShowInspector = useCallback((v: boolean) => {
    setPrefs((p) => (p.showInspector === v ? p : { ...p, showInspector: v }));
  }, []);
  const toggleInspector = useCallback(() => {
    setPrefs((p) => ({ ...p, showInspector: !p.showInspector }));
  }, []);

  const setInspectorWidth = useCallback((v: number) => {
    const inspectorWidth = clampPanelWidth(
      v,
      INSPECTOR_WIDTH_MIN,
      INSPECTOR_WIDTH_MAX,
      INSPECTOR_WIDTH_DEFAULT,
    );
    setPrefs((p) => (p.inspectorWidth === inspectorWidth ? p : { ...p, inspectorWidth }));
  }, []);

  return (
    <LayoutPrefsContext.Provider
      value={{
        ...prefs,
        setShowLibrary,
        toggleLibrary,
        setShowBinder,
        toggleBinder,
        setShowInspector,
        toggleInspector,
        setInspectorWidth,
      }}
    >
      {children}
    </LayoutPrefsContext.Provider>
  );
}

export function useLayoutPrefs(): LayoutPrefs {
  const ctx = useContext(LayoutPrefsContext);
  if (!ctx) throw new Error("useLayoutPrefs must be used within LayoutPrefsProvider");
  return ctx;
}
