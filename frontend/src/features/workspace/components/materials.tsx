"use client";
import { useWorkspace } from "../context";
import { api } from "@/services/api";

export function Materials() {
  const {
    journey,
    tab,
    busy,
    setNotice,
    files,
    setFiles,
    setGuide,
    setQuestion,
    setFeedback,
    materials,
    loadJourney,
    run,
  } = useWorkspace();
  if (!journey) return null;
  return (
    <>
      {" "}
      {tab === "Materials" && (
        <>
          <h2>Build your learning library.</h2>
          <p>
            Upload resources now; processing continues in the background.
            Your plan updates when each resource is ready, and your previous work stays saved.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run("Uploading your resources…", async () => {
                const failed: File[] = [];
                const notices: string[] = [];
                for (const file of files) {
                  try {
                    const result = await api.upload(journey, file);
                    notices.push(`${result.name} uploaded. Processing will continue in the background.`);
                  } catch (e) {
                    failed.push(file);
                    notices.push(
                      `${file.name}: ${e instanceof Error ? e.message : "Upload failed"}`,
                    );
                  }
                }
                setFiles(failed);
                setGuide(null);
                setQuestion(null);
                setFeedback(null);
                await loadJourney();
                setNotice(notices.join(" "));
              });
            }}
          >
            <label className="upload-box" htmlFor="material">
              <span className="upload-icon">↑</span>
              <strong>
                {files.length
                  ? `${files.length} selected resource(s)`
                  : "Choose learning resources"}
              </strong>
              <span>PDF, DOCX, TXT, MD · audio or video</span>
              <input
                id="material"
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.md,.mp3,.wav,.m4a,.mp4,.avi,.mov,.mkv"
                onChange={(e) => setFiles(Array.from(e.target.files || []))}
              />
            </label>
            <p className="small">
              Default limit per file: 20 MiB. Recordings: up to 30 minutes.
              Video uses its audio track.
            </p>
            <button disabled={!!busy || !files.length}>Add resources →</button>
          </form>
          <div className="material-list">
            {materials.map((m) => (
              <div key={m.id}>
                <strong>{m.name}</strong>
                <span role="status" className="break-words">
                  {(m.status || 'ready') === 'ready' ? `${m.passages} passages ? ${m.plan_pending ? 'Updating plan' : 'Ready'}` : m.progress || (m.status === 'failed' ? 'Processing stopped' : 'Waiting to process')}
                </span>
                {m.error && <p className="error break-words" role="alert">{m.error}{m.reference ? ` Reference: ${m.reference}` : ''}</p>}
                {m.plan_error && <p className="small break-words">{m.plan_error}</p>}
                {m.status === 'failed' && <button disabled={!!busy} onClick={() => {
                  void run('Scheduling processing...', async () => {
                    await api.retryDocument(journey, m.id);
                    await loadJourney();
                    setNotice(`${m.name} will resume from its saved progress.`);
                  });
                }}>Retry processing</button>}
              </div>
            ))}
          </div>
        </>
      )}{" "}
    </>
  );
}
