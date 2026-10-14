"use client";
import { useWorkspace } from "../context";
import { api } from "@/services/api";
import { goals } from "../config";

export function JourneySetup() {
  const {
    session,
    goal,
    setGoal,
    subject,
    setSubject,
    busy,
    run,
  } = useWorkspace();
  return (
    <section className="panel">
      <h2>What are you working towards?</h2>
      <p>Start another journey without losing your existing progress.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run("Creating your journey…", async () =>
            session.created(await api.create(goal, subject.trim())),
          );
        }}
      >
        <div className="goal-grid">
          {goals.map((g) => (
            <label
              className={`goal-card ${goal === g.value ? "selected" : ""}`}
              key={g.value}
            >
              <input
                type="radio"
                name="goal"
                checked={goal === g.value}
                onChange={() => setGoal(g.value)}
              />
              <strong>{g.title}</strong>
              <span>{g.text}</span>
            </label>
          ))}
        </div>
        <label htmlFor="subject">Subject, field, or role</label>
        <input
          id="subject"
          required
          maxLength={200}
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="Biology, backend engineering, or data analysis"
        />
        <button disabled={!!busy || !subject.trim()}>Start my journey →</button>
      </form>
    </section>
  );
}
