import type { ThreadBrief } from "@/lib/types";

/** A thread (a difficulty followed until it is overcome) as a small tag. */
export function ThreadChip({ thread }: { thread: ThreadBrief }) {
  const closed = thread.status === "closed";
  return (
    <span
      className={`inline-block max-w-full truncate rounded-full border px-2.5 py-0.5 text-[length:var(--text-small)] ${
        closed ? "border-active/50 text-active" : "border-line-strong text-muted"
      }`}
    >
      {thread.title}
    </span>
  );
}
