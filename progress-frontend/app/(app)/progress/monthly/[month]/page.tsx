"use client";

import { useParams } from "next/navigation";

import { MonthlySummaryView } from "@/components/MonthlySummaryCard";

/** The whole summary of one month, /progress/monthly/2026-09. */
export default function MonthlyPage() {
  const { month } = useParams<{ month: string }>();
  return <MonthlySummaryView month={month} />;
}
