import { forwardRef, useMemo, useRef } from "react";
import CodeMirror, { EditorView, type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { Decoration } from "@codemirror/view";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { search } from "@codemirror/search";
import { typewriterScroll, typewriterTheme, vanishingLines } from "./manuscriptExtensions";
import { mentionAutocompleteExtension, type MentionTarget } from "../lib/mentions";
import type { AnnotationStage, CommentItem } from "../api/client";
import { computeHighlightRanges } from "../lib/annotations";

const manuscriptTheme = EditorView.theme({
  "&": { backgroundColor: "transparent", color: "var(--color-ink-text)" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--font-prose)", lineHeight: "1.85", overflow: "visible" },
  ".cm-content": {
    fontFamily: "var(--font-prose)",
    fontSize: "var(--editor-size, 1.075rem)",
    padding: "0",
    caretColor: "var(--color-amber-deep)",
  },
  ".cm-line": { padding: "0 2px", transition: "opacity 0.12s ease" },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--color-amber-deep)", borderLeftWidth: "2px" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {
    backgroundColor: "color-mix(in srgb, var(--color-amber) 28%, transparent)",
  },
  ".cm-placeholder": { color: "var(--color-paper-muted)" },
});

export interface EditorSelectionInfo {
  from: number;
  to: number;
  text: string;
}

const MarkdownEditor = forwardRef<
  ReactCodeMirrorRef,
  {
    value: string;
    onChange: (v: string) => void;
    placeholder?: string;
    typewriter?: boolean;
    vanishing?: boolean;
    className?: string;
    mentionTargets?: MentionTarget[];
    onSelectionChange?: (sel: EditorSelectionInfo | null) => void;
    annotations?: CommentItem[];
    annotationStage?: AnnotationStage;
    focusAnnotationId?: string | null;
  }
>(({
  value, onChange, placeholder, typewriter = false, vanishing = false, className, mentionTargets,
  onSelectionChange, annotations = [], annotationStage, focusAnnotationId,
}, ref) => {
  const onSelectionRef = useRef(onSelectionChange);
  onSelectionRef.current = onSelectionChange;

  const extensions = useMemo(() => {
    const ex = [
      markdown({ base: markdownLanguage }),
      EditorView.lineWrapping,
      search({ top: true }),
      manuscriptTheme,
      EditorView.updateListener.of((update) => {
        if (!onSelectionRef.current) return;
        if (!update.selectionSet && !update.docChanged) return;
        const main = update.state.selection.main;
        if (main.empty) {
          onSelectionRef.current(null);
          return;
        }
        onSelectionRef.current({
          from: main.from,
          to: main.to,
          text: update.state.sliceDoc(main.from, main.to),
        });
      }),
    ];
    if (mentionTargets?.length) {
      ex.push(mentionAutocompleteExtension(mentionTargets));
    }
    if (annotationStage && annotations.length > 0) {
      const decorations = computeHighlightRanges(value, annotations, annotationStage).map((range) => {
        const focused = range.id === focusAnnotationId;
        return Decoration.mark({
          class: focused ? "cm-annotation-highlight cm-annotation-highlight-focused" : "cm-annotation-highlight",
          attributes: {
            title: range.body,
            "data-annotation-id": range.id,
          },
        }).range(range.start, range.end);
      });
      ex.push(EditorView.decorations.of(Decoration.set(decorations, true)));
    }
    if (typewriter) {
      ex.push(typewriterScroll(), typewriterTheme);
    }
    if (vanishing) {
      ex.push(vanishingLines());
    }
    return ex;
  }, [typewriter, vanishing, mentionTargets, annotations, annotationStage, focusAnnotationId, value]);

  return (
    <CodeMirror
      ref={ref}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      theme="none"
      className={className}
      basicSetup={{
        lineNumbers: false,
        foldGutter: false,
        highlightActiveLine: false,
        highlightActiveLineGutter: false,
        drawSelection: true,
        bracketMatching: false,
        indentOnInput: false,
      }}
      extensions={extensions}
    />
  );
});

MarkdownEditor.displayName = "MarkdownEditor";
export default MarkdownEditor;
