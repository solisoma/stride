"use client";
import { useWorkspace } from "../context";

export function Notifications() {
  const { busy, error, notice } = useWorkspace();
  return (
    <>
      {" "}
      <div aria-live="polite">
        {busy && <p className="status">{busy} Please keep this page open.</p>}
        {notice && <p className="success">{notice}</p>}
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}{" "}
    </>
  );
}
