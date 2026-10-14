"use client";
import { useWorkspace } from "../context";
import { api } from "@/services/api";

export function LearningPlan() {
  const {
    journey,
    tab,
    setTab,
    busy,
    setTopic,
    setGuide,
    setQuestion,
    setFeedback,
    plan,
    materials,
    loadJourney,
    run,
  } = useWorkspace();
  if (!journey) return null;
  return (
    <>
      {" "}
      {tab === "Plan" && (
        <>
          <div className="section-heading">
            <div>
              <h2>Your learning map</h2>
              <p>
                Cover new topics, strengthen gaps, and revisit earlier learning.
              </p>
            </div>
            <button
              disabled={!!busy || !materials.length}
              onClick={() =>
                void run("Refreshing your learning map…", async () => {
                  await api.rebuild(journey);
                  await loadJourney();
                })
              }
            >
              Rebuild plan
            </button>
          </div>
          {plan && (
            <>
              <p className="small">{plan.note}</p>
              {plan.status !== "ready" && (
                <p className="status">
                  Your materials are saved. Rebuild the plan to bring it up to
                  date.
                </p>
              )}
              <div className="topic-list">
                {plan.topics.map((t) => (
                  <article key={t.id}>
                    <div>
                      <strong>
                        {t.title}
                        {!t.active ? " (earlier plan)" : ""}
                      </strong>
                      <p>
                        {t.status.replaceAll("_", " ")} · {t.attempts}{" "}
                        attempt(s){t.due ? " · Due for reassessment" : ""}
                      </p>
                    </div>
                    <button
                      className="text-button"
                      disabled={!!busy}
                      onClick={() => {
                        setTopic(t.title);
                        setTab("Study");
                        setGuide(null);
                      }}
                    >
                      Study →
                    </button>
                    <button
                      className="text-button"
                      disabled={!!busy}
                      onClick={() => {
                        setTopic(t.title);
                        setTab("Learn");
                        setQuestion(null);
                        setFeedback(null);
                      }}
                    >
                      Practise →
                    </button>
                  </article>
                ))}
              </div>
            </>
          )}
        </>
      )}{" "}
    </>
  );
}
