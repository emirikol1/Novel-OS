/** Gold star when AI results are ready for user review. */
export default function PendingAiStar({ title }: { title?: string }) {
  const label = title ?? "AI results ready to review";
  return (
    <span
      className="inline-flex shrink-0 items-center text-[12px] leading-none text-amber-deep"
      {...(title != null ? { title } : {})}
      aria-label={label}
    >
      ★
    </span>
  );
}
