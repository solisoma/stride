"use client";
import { useWorkspace } from "../context";

export function Overview() {
  const {
    journey,
    tab,
    setTab,
    setTopic,
    setQuestion,
    setFeedback,
    progress,
    materials,
    activeTopics,
    needsWork,
    dueTopics,
  } = useWorkspace();
  if (!journey) return null;
  return (
    <>
      {" "}
      {tab === "Dashboard" && (
        <div className="dashboard-content">
          <div className="stats-grid">
            <div className="stat-card">
              <span>Learning resources</span>
              <strong>{materials.length}</strong>
              <small>In this journey</small>
            </div>
            <div className="stat-card">
              <span>Practice attempts</span>
              <strong>{progress?.attempts.length || 0}</strong>
              <small>Saved with feedback</small>
            </div>
            <div className="stat-card">
              <span>Topics to strengthen</span>
              <strong>{needsWork.length}</strong>
              <small>Based on your attempts</small>
            </div>
            <div className="stat-card">
              <span>Ready to revisit</span>
              <strong>{dueTopics.length}</strong>
              <small>Check your retention</small>
            </div>
          </div>
          <div className="dashboard-grid">
            <article className="dashboard-card">
              <div className="section-heading">
                <h2>Your learning path</h2>
                <button className="text-button" onClick={() => setTab("Plan")}>
                  View map &rarr;
                </button>
              </div>
              {activeTopics.length ? (
                activeTopics.slice(0, 5).map((t, i) => (
                  <button
                    className="path-row"
                    key={t.id}
                    onClick={() => {
                      setTopic(t.title);
                      setTab("Learn");
                      setQuestion(null);
                      setFeedback(null);
                    }}
                  >
                    <span className="path-number">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span>
                      <strong>{t.title}</strong>
                      <small>{t.status.replaceAll("_", " ")}</small>
                    </span>
                    <span aria-hidden="true">&#8594;</span>
                  </button>
                ))
              ) : (
                <div className="empty">
                  <strong>Your path starts with your materials.</strong>
                  <p>Upload a resource to build your first learning map.</p>
                  <button onClick={() => setTab("Materials")}>
                    Add materials &rarr;
                  </button>
                </div>
              )}
            </article>
            <article className="dashboard-card">
              <div className="section-heading">
                <h2>Recent activity</h2>
                <button
                  className="text-button"
                  onClick={() => setTab("Progress")}
                >
                  View all &rarr;
                </button>
              </div>
              {progress?.attempts.length ? (
                [...progress.attempts]
                  .reverse()
                  .slice(0, 4)
                  .map((a) => (
                    <div className="activity-row" key={a.id}>
                      <span
                        className={`activity-dot ${a.feedback.verdict === "correct" ? "correct" : ""}`}
                      />
                      <div>
                        <strong>{a.topic}</strong>
                        <small>
                          {a.feedback.verdict.replaceAll("_", " ")}
                          {a.created_at
                            ? ` - ${new Date(a.created_at * 1000).toLocaleDateString()}`
                            : ""}
                        </small>
                      </div>
                    </div>
                  ))
              ) : (
                <div className="empty">
                  <strong>Your progress belongs here.</strong>
                  <p>
                    Complete a scenario to see your feedback and next steps.
                  </p>
                  <button
                    className="text-button"
                    onClick={() => setTab("Learn")}
                  >
                    Open practice & chat &rarr;
                  </button>
                </div>
              )}
            </article>
          </div>
          <div className="quick-actions">
            <button onClick={() => setTab("Study")}>
              Read a focused guide <span aria-hidden="true">&rarr;</span>
            </button>
            <button onClick={() => setTab("Learn")}>
              Practise or ask a question <span aria-hidden="true">&rarr;</span>
            </button>
            <button onClick={() => setTab("Materials")}>
              Add a learning resource <span>+</span>
            </button>
          </div>
        </div>
      )}{" "}
    </>
  );
}
