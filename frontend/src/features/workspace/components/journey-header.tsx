"use client";
import { useWorkspace } from "../context";

export function JourneyHeader() {
  const { journey, tab, busy, plan, follow, next } =
    useWorkspace();
  if (!journey) return null;
  return (
    <>
      {" "}
      <div className="journey-bar">
        <div>
          <span className="eyebrow">YOUR LEARNING JOURNEY</span>
          <h2>{journey.subject}</h2>
        </div>
        <span className="small">Material revision {plan?.revision ?? "…"}</span>
      </div>
      {tab === "Dashboard" && next && (
        <aside className="next-card">
          <div>
            <span className="eyebrow">RECOMMENDED NEXT STEP</span>
            <h3>{next.topic || "Build your learning map"}</h3>
            <p>{next.reason}</p>
          </div>
          <button disabled={!!busy} onClick={() => follow(next)}>
            Take this step →
          </button>
        </aside>
      )}{" "}
    </>
  );
}
