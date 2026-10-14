import type { ReactNode } from "react";
import { DashboardProvider } from "@/features/workspace/dashboard-provider";
export default function DashboardLayout({ children }: { children: ReactNode }) {
  return <DashboardProvider>{children}</DashboardProvider>;
}
