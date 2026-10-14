"use client";
import type { ReactNode } from "react";
import Link from "next/link";
import { useWorkspace } from "@/features/workspace/context";
import { JourneyHeader } from "@/features/workspace/components/journey-header";
export default function JourneyLayout({ children }: { children: ReactNode }) {
  const { journey, tab } = useWorkspace();
  if (!journey)
    return (
      <section className="panel">
        <h2>Journey not available</h2>
        <p>
          This journey does not belong to your account or could not be loaded.
        </p>
        <Link href="/dashboard">Back to your journeys</Link>
      </section>
    );
  return (
    <>
      <JourneyHeader />
      <section
        className={`panel ${tab === "Study" || tab === "Learn" ? "learning-panel" : ""}`}
      >
        {children}
      </section>
    </>
  );
}
