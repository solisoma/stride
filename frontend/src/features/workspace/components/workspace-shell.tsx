"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { useWorkspace } from "../context";
import {
  goals,
  tabs,
  sectionNames,
  navSymbols,
  workspaceHref,
} from "../config";
import { Notifications } from "./notifications";

export function WorkspaceShell({ children }: { children: ReactNode }) {
  const {
    user,
    journey,
    journeys,
    session,
    tab,
    busy,
    setNotice,
    setError,
    run,
  } = useWorkspace();
  const navigationJourney = journey || session.journey || journeys[0] || null;
  return (
    <div className={user ? "shell dashboard-shell" : "shell welcome-shell"}>
      {user && (
        <aside className="sidebar">
          <a className="brand" href="/">
            Stride
            <span className="brand-mark">&#8599;</span>
          </a>
          <span className="sidebar-label">WORKSPACE</span>
          <nav aria-label="Workspace navigation">
            {tabs.map((item) => (
              <Link
                href={workspaceHref(item, navigationJourney?.id)}
                key={item}
                aria-current={tab === item ? "page" : undefined}
                aria-disabled={
                  !!busy || (!navigationJourney && item !== "Dashboard")
                }
                className={tab === item ? "active" : ""}
                onClick={(event) => {
                  if (busy || (!navigationJourney && item !== "Dashboard")) {
                    event.preventDefault();
                    return;
                  }
                  setNotice("");
                  setError("");
                }}
              >
                <span className="nav-symbol" aria-hidden="true">
                  {navSymbols[item]}
                </span>
                {item === "Learn" ? "Practice" : item}
              </Link>
            ))}
          </nav>
          <div className="sidebar-journeys">
            <label htmlFor="journey">CURRENT JOURNEY</label>
            <select
              id="journey"
              disabled={!!busy}
              value={journey?.id || ""}
              onChange={(e) =>
                session.select(
                  journeys.find((j) => j.id === Number(e.target.value)) || null,
                )
              }
            >
              <option value="">Choose a journey</option>
              {journeys.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.subject}
                </option>
              ))}
            </select>
            <button
              className="new-journey"
              disabled={!!busy}
              onClick={() => session.select(null)}
            >
              + New journey
            </button>
          </div>
          <div className="sidebar-bottom">
            <span className="eyebrow">SMALL STEPS. REAL PROGRESS.</span>
            <p>Keep showing up for what comes next.</p>
          </div>
        </aside>
      )}
      <header className="topbar">
        <a className="brand" href="/">
          Stride
          <span className="brand-mark">↗</span>
        </a>
        {user ? (
          <div className="account-bar">
            <span>
              {user.name}
              {user.role === "admin" ? " - Admin" : ""}
            </span>
            <button
              className="text-button"
              disabled={!!busy}
              onClick={() => void run("Signing out…", session.logout)}
            >
              Sign out
            </button>
          </div>
        ) : (
          <span className="header-note">
            A little clarity. A lot of progress.
          </span>
        )}
      </header>
      <main>
        {user ? (
          <div className="workspace-heading">
            <div>
              <span className="eyebrow">
                YOUR WORKSPACE / {tab.toUpperCase()}
              </span>
              <h1>
                {journey ? sectionNames[tab] : "Start something meaningful."}
              </h1>
              <p>
                {tab === "Dashboard"
                  ? `Welcome back, ${user.name.split(" ")[0]}. Pick up where you left off.`
                  : tab === "Learn"
                    ? "Solve a scenario, ask a question, and work through the explanation in one place."
                    : "Make your next learning step a useful one."}
              </p>
            </div>
            <span className="workspace-chip">
              {journey
                ? goals.find((g) => g.value === journey.goal)?.title
                : "New journey"}
            </span>
          </div>
        ) : (
          <div className="intro">
            <span className="eyebrow">YOUR NEXT STEP STARTS HERE</span>
            <h1>
              Make learning
              <br />
              <em>move you forward.</em>
            </h1>
            <p>Focused reading. Practice that learns from your mistakes.</p>
          </div>
        )}
        {children}
        <Notifications />
      </main>
      <footer>
        <span>Stride</span>
        <span>Read with focus. Practise with purpose.</span>
      </footer>
    </div>
  );
}
