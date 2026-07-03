import type { ParagraphFormat } from "./chapterBrief";

export function manuscriptParagraphFormat(value?: string | null): ParagraphFormat {
  return value === "indented" ? "indented" : "block";
}

export function manuscriptProseClassName(
  paragraphFormat?: string | null,
  baseClassName = "prose-manuscript",
): string {
  const format = manuscriptParagraphFormat(paragraphFormat);
  return format === "indented"
    ? `${baseClassName} prose-manuscript--indented`
    : baseClassName;
}
