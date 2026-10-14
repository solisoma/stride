"use client";
import { useWorkspace } from "../context";
import { api } from "@/services/api";
import { SourceReview } from "@/components/source-review";

export function SourceReviews() {
  const {
    journey,
    tab,
    busy,
    setNotice,
    setGuide,
    setQuestion,
    setFeedback,
    reviews,
    loadJourney,
    run,
  } = useWorkspace();
  if (!journey) return null;
  return (
    <>
      {" "}
      {(tab === "Materials" || tab === "Plan") && reviews.length > 0 && (
        <section className="review-list">
          <h2>Source questions to resolve</h2>
          {reviews.map((r) => (
            <SourceReview
              key={`${r.id}-${r.decision}`}
              review={r}
              busy={!!busy}
              onDecision={(id, decision, note) =>
                void run(
                  "Saving your choice and updating the plan…",
                  async () => {
                    const result = await api.decide(
                      journey,
                      id,
                      decision,
                      note,
                    );
                    setQuestion(null);
                    setFeedback(null);
                    setGuide(null);
                    await loadJourney();
                    setNotice(
                      result.plan_error ||
                        "Choice saved. New learning uses your preference, with uncertainty kept visible.",
                    );
                  },
                )
              }
            />
          ))}
        </section>
      )}{" "}
    </>
  );
}
