"use client";

import { Button } from "@/components/ui";

/** Up to five suggested answers; pressing one sends it as the person's message. */
export function QuickReplies({
  options,
  onPick,
  disabled,
}: {
  options: string[];
  onPick: (text: string, index: number) => void;
  disabled?: boolean;
}) {
  if (!options.length) return null;
  return (
    <div className="enter flex flex-wrap gap-2 pt-1">
      {options.slice(0, 5).map((option, index) => (
        <Button
          key={option}
          variant="quiet"
          disabled={disabled}
          onClick={() => onPick(option, index)}
          className="max-w-full text-left"
        >
          {option}
        </Button>
      ))}
    </div>
  );
}
