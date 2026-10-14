"use client";
import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { WorkspaceProvider } from "./context";
import { useWorkspaceController } from "./use-workspace";
import { WorkspaceSkeleton } from "./components/workspace-skeleton";
import { WorkspaceShell } from "./components/workspace-shell";

export function DashboardProvider({ children }: { children: ReactNode }) {
  const workspace = useWorkspaceController();
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (workspace.ready && !workspace.user)
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [workspace.ready, workspace.user, pathname, router]);
  if (!workspace.ready || !workspace.user || workspace.journeyLoading)
    return <WorkspaceSkeleton />;
  return (
    <WorkspaceProvider value={workspace}>
      <WorkspaceShell>{children}</WorkspaceShell>
    </WorkspaceProvider>
  );
}
