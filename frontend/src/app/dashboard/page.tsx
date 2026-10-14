"use client";
import Link from "next/link";
import { useWorkspace } from "@/features/workspace/context";
import { LegacyImport } from "@/features/workspace/components/legacy-import";
export default function DashboardPage() {
  const { journeys } = useWorkspace();
  return (
    <>
      <LegacyImport />
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Your journeys</h2>
            <p>Continue learning or start with a new goal.</p>
          </div>
          <Link
            className="rounded-lg bg-[#183832] px-5 py-3 text-sm text-white"
            href="/dashboard/new"
          >
            New journey +
          </Link>
        </div>
        <div className="grid gap-4 pt-6 sm:grid-cols-2">
          {journeys.map((j) => (
            <Link
              className="rounded-xl border border-[#dce3d9] p-6 hover:bg-[#f0f6e7]"
              key={j.id}
              href={`/dashboard/journeys/${j.id}`}
            >
              <h3>{j.subject}</h3>
              <p className="small">{j.goal.replaceAll("_", " ")}</p>
              <span className="text-sm">Continue learning →</span>
            </Link>
          ))}
        </div>
        {!journeys.length && (
          <p>
            Your first journey starts with a goal and your learning materials.
          </p>
        )}
      </section>
    </>
  );
}
