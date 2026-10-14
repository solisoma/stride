"use client";
import { useWorkspace } from "../context";
import ReactMarkdown from "react-markdown";
import { api } from "@/services/api";
import { Sources } from "@/components/sources";
import { ChatPanel } from "@/components/chat-panel";

export function Study() {
  const {
    journey,
    tab,
    setTab,
    busy,
    topic,
    setTopic,
    guide,
    setGuide,
    setQuestion,
    setFeedback,
    materials,
    activities,
    messages,
    message,
    setMessage,
    chatOpen,
    setChatOpen,
    chatInput,
    loadJourney,
    run,
    download,
    } = useWorkspace();
  if (!journey) return null;
  return (
    <>
      {" "}
      {tab === "Study" && (
        <div className="learning-grid">
          <section className="practice-column study-column">
            <div className="workspace-section-label">
              <span className="eyebrow">STUDY</span>
              <span className="small">Read, ask, understand</span>
            </div>{" "}
            {tab === "Study" && (
              <>
                <h2>A focused place to start.</h2>
                <p>Choose a topic or use the recommended next step.</p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void run("Preparing your guide...", async () => {
                      setGuide(await api.guide(journey, topic.trim()));
                      await loadJourney();
                    });
                  }}
                >
                  <label htmlFor="topic">Topic</label>
                  <input
                    id="topic"
                    required
                    maxLength={300}
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Binary search or cellular respiration"
                  />
                  <button disabled={!!busy || !topic.trim()}>
                    Create focused guide &rarr;
                  </button>
                </form>
              </>
            )}
            {tab === "Study" && guide && (
              <article className="output">
                <div className="section-heading">
                  <h3>{guide.title || "Your focused guide"}</h3>
                  <button className="text-button" onClick={download}>
                    Download ↓
                  </button>
                </div>
                <ReactMarkdown>{guide.content}</ReactMarkdown>
                <Sources sources={guide.sources} citations={guide.citations} />
                <button
                  disabled={!!busy}
                  onClick={() => {
                    setTab("Learn");
                    setQuestion(null);
                    setFeedback(null);
                  }}
                >
                  Practise this topic →
                </button>
              </article>
            )}
            {tab === "Study" && (
              <details className="sources">
                <summary>Saved guides</summary>
                {activities
                  .filter((a) => a.kind === "guide")
                  .map((a) => (
                    <button
                      className="saved-guide"
                      key={a.id}
                      disabled={!!busy}
                      onClick={() => {
                        setTopic(a.topic);
                        setGuide({
                          id: a.id,
                          title: a.result.title,
                          content: a.result.content || "",
                          citations: a.result.citations || [],
                          sources: a.sources,
                        });
                      }}
                    >
                      <span>{a.topic}</span>
                      <span className="small">
                        {a.stale
                          ? "Earlier material revision — regenerate to update"
                          : "Current materials"}
                      </span>
                    </button>
                  ))}
              </details>
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
              guide ? `Reading: ${guide.title || topic}` : "Ask while you study"
            }
            onSend={() =>
              void run("Explaining your study material...", async () => {
                await api.chat(journey, message.trim(), guide?.id);
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
