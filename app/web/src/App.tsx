import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import BackgroundJobHost from "./components/BackgroundJobHost";
import Sidebar from "./components/Sidebar";
import CommandPalette from "./components/CommandPalette";
import ShortcutsHelp from "./components/ShortcutsHelp";
import ErrorBoundary from "./components/ErrorBoundary";
import { ToastProvider } from "./components/Toaster";
import { ConfirmProvider } from "./components/Confirm";
import { LayoutPrefsProvider, useLayoutPrefs } from "./context/LayoutPrefs";
import { ToolTipProvider } from "./context/ToolTipContext";
import ToolTipDock from "./components/ToolTipDock";

// Code-split routes so the CodeMirror editor only loads on the chapter view.
const ProjectsList = lazy(() => import("./routes/ProjectsList"));
const ProjectDashboard = lazy(() => import("./routes/ProjectDashboard"));
const ChapterView = lazy(() => import("./routes/ChapterView"));
const HelpGuide = lazy(() => import("./routes/HelpGuide"));

export function routeAnimationKey(pathname: string): string {
  const match = pathname.match(/^\/projects\/([^/]+)\/chapters\/[^/]+$/);
  if (!match) return pathname;
  return `/projects/${match[1]}/chapters`;
}

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={routeAnimationKey(location.pathname)}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        className="h-full"
      >
        <Suspense fallback={<div className="px-10 py-12 text-ink-muted">Loading…</div>}>
          <Routes location={location}>
            <Route path="/" element={<ProjectsList />} />
            <Route path="/help" element={<HelpGuide />} />
            <Route path="/help/:topic" element={<HelpGuide />} />
            <Route path="/projects/:id" element={<ProjectDashboard />} />
            <Route path="/projects/:id/chapters/:n" element={<ChapterView />} />
          </Routes>
        </Suspense>
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <MotionConfig reducedMotion="user">
        <ToastProvider>
          <ConfirmProvider>
            <LayoutPrefsProvider>
              <ToolTipProvider>
                <BackgroundJobHost />
                <AppShell />
                <ToolTipDock />
              </ToolTipProvider>
            </LayoutPrefsProvider>
          </ConfirmProvider>
        </ToastProvider>
      </MotionConfig>
    </BrowserRouter>
  );
}

function AppShell() {
  const { showLibrary } = useLayoutPrefs();
  return (
    <>
      <a href="#main" className="skip-link">Skip to content</a>
      <CommandPalette />
      <ShortcutsHelp />
      <div className="flex h-full">
        {showLibrary && <Sidebar />}
        <main id="main" className="h-full flex-1 overflow-y-auto">
          <ErrorBoundary>
            <AnimatedRoutes />
          </ErrorBoundary>
        </main>
      </div>
    </>
  );
}
