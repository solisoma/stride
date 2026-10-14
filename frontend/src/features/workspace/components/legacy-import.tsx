"use client";
import { useWorkspace } from "../context";
import { api } from "@/services/api";

export function LegacyImport() {
  const { session, journey, busy, legacy, setLegacy, run } =
    useWorkspace();
  if (!journey) return null;
  return (
    <>
      {" "}
      {legacy && (
        <div className="legacy-banner">
          <p>
            Bring your earlier prototype journey into this account, including
            its saved progress.
          </p>
          <button
            disabled={!!busy}
            onClick={() =>
              void run("Importing your earlier journey…", async () => {
                const j = await api.claim(legacy.id, legacy.access_token);
                localStorage.removeItem("learnforward.journey");
                setLegacy(null);
                await session.created(j);
              })
            }
          >
            Import earlier journey
          </button>
          <button className="text-button" onClick={() => setLegacy(null)}>
            Later
          </button>
        </div>
      )}{" "}
    </>
  );
}
