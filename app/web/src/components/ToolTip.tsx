import {
  cloneElement,
  isValidElement,
  useCallback,
  type ReactElement,
  type ReactNode,
} from "react";
import {
  HOVER_DELAY_MS,
  useToolTipContext,
  useToolTipToken,
} from "../context/ToolTipContext";
import type { ToolTipId } from "../lib/toolRegistry";
import { TOOLTIP_DOCK_ID } from "./ToolTipDock";

export { HOVER_DELAY_MS };

export default function ToolTip({
  id,
  children,
  className,
}: {
  id: ToolTipId;
  children: ReactNode;
  className?: string;
}) {
  const { activeId, scheduleActive, clearActive, scheduleDismiss } = useToolTipContext();
  const token = useToolTipToken();
  const visible = activeId === id;

  const show = useCallback(() => {
    scheduleActive(id, token);
  }, [id, scheduleActive, token]);

  const hide = useCallback(() => {
    if (activeId === id) {
      scheduleDismiss(token);
    } else {
      clearActive(token);
    }
  }, [activeId, clearActive, id, scheduleDismiss, token]);

  type AnchorProps = React.HTMLAttributes<HTMLElement> & {
    ref?: React.Ref<HTMLElement>;
  };

  const child = isValidElement(children)
    ? (() => {
        const childElement = children as ReactElement<AnchorProps>;
        return cloneElement(childElement, {
          ref: childElement.props.ref,
          onMouseEnter: (e) => {
            childElement.props.onMouseEnter?.(e as React.MouseEvent<HTMLElement>);
            show();
          },
          onMouseLeave: (e) => {
            childElement.props.onMouseLeave?.(e as React.MouseEvent<HTMLElement>);
            hide();
          },
          onFocus: (e) => {
            childElement.props.onFocus?.(e as React.FocusEvent<HTMLElement>);
            if ((e.target as HTMLElement).matches(":focus-visible")) show();
          },
          onBlur: (e) => {
            childElement.props.onBlur?.(e as React.FocusEvent<HTMLElement>);
            hide();
          },
          "aria-describedby": visible ? TOOLTIP_DOCK_ID : undefined,
        });
      })()
    : (
      <span
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={(e) => {
          if ((e.target as HTMLElement).matches(":focus-visible")) show();
        }}
        onBlur={hide}
        aria-describedby={visible ? TOOLTIP_DOCK_ID : undefined}
      >
        {children}
      </span>
    );

  return <span className={className ?? "inline-flex items-center gap-1"}>{child}</span>;
}
