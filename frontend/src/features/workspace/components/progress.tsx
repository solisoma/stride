"use client";
import { useWorkspace } from "../context";
import ReactMarkdown from "react-markdown";
import { Sources } from "@/components/sources";

export function ProgressHistory() {
  const { tab, progress } = useWorkspace();
  return (
    <>
      {" "}
      {tab === "Progress" && (
        <>
          <h2>Your learning history</h2>
          <p>
            Saved answers and next steps, including earlier material revisions.
          </p>
          {progress && (
            <>
              <p className="small">{progress.note}</p>
              {!progress.attempts.length ? (
                <div className="empty">
                  Your first scenario starts your practice history.
                </div>
              ) : (
                [...progress.attempts].reverse().map((a) => (
                  <details className="attempt" key={a.id}>
                    <summary>
                      {a.topic}
                      <span>{a.feedback.verdict.replaceAll("_", " ")}</span>
                    </summary>
                    <p className="small">
                      {a.created_at
                        ? new Date(a.created_at * 1000).toLocaleString()
                        : "Earlier attempt"}{" "}
                      · Revision {a.revision} ·{" "}
                      {a.supported === null
                        ? "Earlier attempt; support not recorded"
                        : a.supported
                          ? "Supported practice"
                          : "Independent attempt"}
                    </p>
                    <h4>Your answer</h4>
                    <pre>{a.answer}</pre>
                    <ReactMarkdown>{a.feedback.explanation}</ReactMarkdown>
                    <h4>Next step</h4>
                    <p>{a.feedback.next_step}</p>
                    <Sources
                      sources={a.sources}
                      citations={a.feedback.citations}
                    />
                  </details>
                ))
              )}
            </>
          )}
        </>
      )}{" "}
    </>
  );
}
