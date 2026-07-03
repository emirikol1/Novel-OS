import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { ToolTipId } from "../lib/toolRegistry";

export const HOVER_DELAY_MS = 700;
export const DISMISS_DELAY_MS = 300;

type Token = number;

type ToolTipContextValue = {
  activeId: ToolTipId | null;
  scheduleActive: (id: ToolTipId, token: Token) => void;
  clearActive: (token: Token) => void;
  scheduleDismiss: (token: Token) => void;
  scheduleDismissActive: () => void;
  holdActive: () => void;
};

const ToolTipContext = createContext<ToolTipContextValue | null>(null);

let nextToken = 1;

export function useToolTipToken(): Token {
  const tokenRef = useRef<Token | null>(null);
  if (tokenRef.current === null) tokenRef.current = nextToken++;
  return tokenRef.current;
}

export function ToolTipProvider({ children }: { children: ReactNode }) {
  const [activeId, setActiveId] = useState<ToolTipId | null>(null);
  const showDelayRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dismissDelayRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRef = useRef<{ id: ToolTipId; token: Token } | null>(null);
  const activeTokenRef = useRef<Token | null>(null);

  const clearShowDelay = useCallback(() => {
    if (showDelayRef.current) {
      clearTimeout(showDelayRef.current);
      showDelayRef.current = null;
    }
  }, []);

  const clearDismissDelay = useCallback(() => {
    if (dismissDelayRef.current) {
      clearTimeout(dismissDelayRef.current);
      dismissDelayRef.current = null;
    }
  }, []);

  const scheduleActive = useCallback(
    (id: ToolTipId, token: Token) => {
      clearShowDelay();
      clearDismissDelay();
      pendingRef.current = { id, token };
      showDelayRef.current = setTimeout(() => {
        if (pendingRef.current?.token === token) {
          activeTokenRef.current = token;
          setActiveId(id);
        }
      }, HOVER_DELAY_MS);
    },
    [clearDismissDelay, clearShowDelay],
  );

  const clearActive = useCallback(
    (token: Token) => {
      clearShowDelay();
      clearDismissDelay();
      if (pendingRef.current?.token === token) pendingRef.current = null;
      if (activeTokenRef.current === token) {
        activeTokenRef.current = null;
        setActiveId(null);
      }
    },
    [clearDismissDelay, clearShowDelay],
  );

  const scheduleDismiss = useCallback(
    (token: Token) => {
      clearShowDelay();
      if (pendingRef.current?.token === token) pendingRef.current = null;
      if (activeTokenRef.current !== token) return;
      clearDismissDelay();
      dismissDelayRef.current = setTimeout(() => {
        if (activeTokenRef.current === token) {
          activeTokenRef.current = null;
          setActiveId(null);
        }
      }, DISMISS_DELAY_MS);
    },
    [clearDismissDelay, clearShowDelay],
  );

  const holdActive = useCallback(() => {
    clearDismissDelay();
  }, [clearDismissDelay]);

  const scheduleDismissActive = useCallback(() => {
    const token = activeTokenRef.current;
    if (token != null) scheduleDismiss(token);
  }, [scheduleDismiss]);

  useEffect(
    () => () => {
      clearShowDelay();
      clearDismissDelay();
    },
    [clearDismissDelay, clearShowDelay],
  );

  return (
    <ToolTipContext.Provider
      value={{ activeId, scheduleActive, clearActive, scheduleDismiss, scheduleDismissActive, holdActive }}
    >
      {children}
    </ToolTipContext.Provider>
  );
}

const noopContext: ToolTipContextValue = {
  activeId: null,
  scheduleActive: () => {},
  clearActive: () => {},
  scheduleDismiss: () => {},
  scheduleDismissActive: () => {},
  holdActive: () => {},
};

export function useToolTipContext(): ToolTipContextValue {
  return useContext(ToolTipContext) ?? noopContext;
}
