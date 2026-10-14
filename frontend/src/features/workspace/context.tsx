"use client";
import { createContext, useContext, type ReactNode } from "react";
import type { WorkspaceState } from "./use-workspace";

const Context = createContext<WorkspaceState | null>(null);
export function WorkspaceProvider({
  value,
  children,
}: {
  value: WorkspaceState;
  children: ReactNode;
}) {
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useWorkspace() {
  const value = useContext(Context);
  if (!value)
    throw new Error("Workspace components must be inside WorkspaceProvider");
  return value;
}
