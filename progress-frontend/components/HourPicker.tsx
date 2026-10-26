"use client";

import { useT } from "@/lib/useT";

const HOURS = Array.from({ length: 18 }, (_, i) => i + 6); // 06:00 - 23:00

/** "I'll pick a time": the chosen hour goes to the conversation as "HH:00". */
export function HourPicker({
  onPick,
  onClose,
}: {
  onPick: (hhmm: string) => void;
  onClose: () => void;
}) {
  const { t } = useT();
  return (
    <div className="enter rounded-md border border-line p-3" role="group" aria-label={t.today.pickHourLabel}>
      <div className="mb-2 flex items-center justify-between">
        <p className="label">{t.today.pickHour}</p>
        <button
          type="button"
          onClick={onClose}
          aria-label={t.notify.later}
          className="press -m-2 p-2 text-label hover:text-bone"
        >
          ✕
        </button>
      </div>
      <div className="grid grid-cols-6 gap-1.5">
        {HOURS.map((h) => {
          const label = `${String(h).padStart(2, "0")}:00`;
          return (
            <button
              key={h}
              type="button"
              onClick={() => onPick(label)}
              className="press rounded-sm border border-line py-2 font-mono text-[length:var(--text-small)] text-bone hover:border-sunrise"
            >
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
