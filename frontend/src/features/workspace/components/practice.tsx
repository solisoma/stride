"use client";
import { useWorkspace } from "../context";
import ReactMarkdown from "react-markdown";
import { api } from "@/services/api";
import { Sources } from "@/components/sources";
import { ChatPanel } from "@/components/chat-panel";

export function Practice() {
  const {
    journey,
    tab,
    setTab,
    busy,
    topic,
    setTopic,
    format,
    setFormat,
    question,
    answer,
    setAnswer,
    feedback,
    setFeedback,
    materials,
    messages,
    message,
    setMessage,
    chatOpen,
    setChatOpen,
    chatInput,
    submission,
    loadJourney,
    run,
    newQuestion,
    } = useWorkspace();
  if (!journey) return null;
  return (
    <>
      {" "}
      {tab === "Learn" && (
        <div className="learning-grid">
          <section className="practice-column">
            <div className="workspace-section-label">
              <span className="eyebrow">PRACTICE</span>
              <span className="small">Apply what you know</span>
            </div>{" "}
            <h2>Put your understanding to work.</h2>
            <p>
              Fresh scenarios target your gaps. Ask your coach whenever you need
              help.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void run("Preparing a fresh scenario...", newQuestion);
              }}
            >
              <label htmlFor="topic">Topic</label>
              <input
                id="topic"
                required
                maxLength={300}
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Choose a concept to practise"
              />
              <label htmlFor="format">Answer format</label>
              <select
                id="format"
                value={format}
                onChange={(e) => setFormat(e.target.value)}
              >
                <option value="typed">Explain in your own words</option>
                <option value="multiple_choice">Multiple choice</option>
              </select>
              <button disabled={!!busy || !topic.trim() || !materials.length}>
                Give me a fresh scenario &rarr;
              </button>
            </form>{" "}
            {tab === "Learn" && question && (
              <article className="output">
                <h3>Your scenario</h3>
                {question.supported && (
                  <p className="small">
                    Follow-up after correction. This records supported practice;
                    a later fresh check will assess independent understanding.
                  </p>
                )}
                <ReactMarkdown>{question.prompt}</ReactMarkdown>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void run("Reviewing your answer…", async () => {
                      setFeedback(
                        await api.answer(
                          journey,
                          question.id,
                          answer.trim(),
                          submission.current,
                        ),
                      );
                      await loadJourney();
                    });
                  }}
                >
                  {question.options.length ? (
                    <fieldset disabled={!!busy || !!feedback}>
                      <legend>Choose an answer</legend>
                      {question.options.map((o, i) => (
                        <label className="option" key={i}>
                          <input
                            type="radio"
                            name="answer"
                            checked={answer === o}
                            onChange={() => setAnswer(o)}
                          />
                          <span>{o}</span>
                        </label>
                      ))}
                    </fieldset>
                  ) : (
                    <>
                      <label htmlFor="answer">Your answer or code</label>
                      <textarea
                        id="answer"
                        rows={7}
                        maxLength={20000}
                        disabled={!!busy || !!feedback}
                        value={answer}
                        onChange={(e) => setAnswer(e.target.value)}
                        placeholder="Explain your reasoning. You can paste code too."
                      />
                    </>
                  )}
                  <button disabled={!!busy || !answer.trim() || !!feedback}>
                    Review my answer →
                  </button>
                </form>
                {feedback && (
                  <div className="feedback">
                    <span className="eyebrow">
                      {feedback.verdict.replaceAll("_", " ")}
                    </span>
                    <ReactMarkdown>{feedback.explanation}</ReactMarkdown>
                    <h4>Your next step</h4>
                    <p>{feedback.next_step}</p>
                    <Sources
                      sources={feedback.sources || []}
                      citations={feedback.citations}
                    />
                    <div className="actions">
                      <button
                        disabled={!!busy}
                        onClick={() =>
                          void run("Preparing a fresh scenario…", newQuestion)
                        }
                      >
                        Try a new scenario
                      </button>
                      <button
                        className="text-button"
                        disabled={!!busy}
                        onClick={() => {
                          setTab("Learn");
                          setMessage(
                            `Explain my mistake on ${question.topic || topic}: ${feedback.explanation}`,
                          );
                          setChatOpen(true);
                        }}
                      >
                        Ask for more explanation
                      </button>
                      {feedback.verdict === "clarification_needed" && (
                        <button
                          className="text-button"
                          onClick={() => {
                            setFeedback(null);
                            submission.current = crypto.randomUUID();
                          }}
                        >
                          Clarify my answer
                        </button>
                      )}
                    </div>
                    <p className="small">
                      Code is reviewed, not executed. Practice results do not
                      guarantee mastery.
                    </p>
                  </div>
                )}
              </article>
            )}
            {!question && (
              <div className="practice-empty">
                <span aria-hidden="true">&#9671;</span>
                <h3>A fresh scenario. A clearer understanding.</h3>
                <p>
                  Choose a topic above to start. You can ask your coach for help
                  without leaving this workspace.
                </p>
              </div>
            )}
          </section>
          <ChatPanel
            open={chatOpen}
            onOpenChange={setChatOpen}
            messages={messages}
            message={message}
            onMessage={setMessage}
            busy={!!busy}
            hasMaterials={!!materials.length}
            topic={topic}
            inputRef={chatInput}
            contextLabel={
              question
                ? `Practising: ${question.topic || topic}`
                : "Questions and explanations"
            }
            onSend={() =>
              void run("Finding an explanation...", async () => {
                await api.chat(journey, message.trim(), question?.id);
                setMessage("");
                await loadJourney();
              })
            }
          />
        </div>
      )}{" "}
    </>
  );
}
