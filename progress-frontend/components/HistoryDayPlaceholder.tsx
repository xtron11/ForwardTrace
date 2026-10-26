"use client";

import { useParams } from "next/navigation";

import { ScreenPlaceholder } from "@/components/ScreenPlaceholder";

export function HistoryDayPlaceholder() {
  const { date } = useParams<{ date: string }>();
  return <ScreenPlaceholder kind="historyDay" detail={date} />;
}
