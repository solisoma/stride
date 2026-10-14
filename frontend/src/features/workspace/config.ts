import type { Goal } from "@/types/learning";

export const goals: { value: Goal; title: string; text: string }[] = [
  {
    value: "exam",
    title: "Prepare for an exam",
    text: "Focus your revision and work through scenarios.",
  },
  {
    value: "technical_interview",
    title: "Prepare for an interview",
    text: "Practise reasoning, concepts, and code.",
  },
  {
    value: "new_field",
    title: "Explore a new field",
    text: "Build understanding, one concept at a time.",
  },
];
export const tabs = [
  "Dashboard",
  "Materials",
  "Plan",
  "Study",
  "Learn",
  "Progress",
] as const;
export type Tab = (typeof tabs)[number];

export const sectionNames: Record<Tab, string> = {
  Dashboard: "Your learning overview",
  Materials: "Learning library",
  Plan: "Learning map",
  Study: "Focused study",
  Learn: "Practice & conversation",
  Progress: "Learning history",
};
export const navSymbols: Record<Tab, string> = {
  Dashboard: "\u25eb",
  Materials: "\u25a4",
  Plan: "\u25c7",
  Study: "\u25a7",
  Learn: "\u2197",
  Progress: "\u25f7",
};

const segments: Record<Tab, string> = {
  Dashboard: "",
  Materials: "materials",
  Plan: "plan",
  Study: "study",
  Learn: "practice",
  Progress: "progress",
};
export function workspaceHref(tab: Tab, journeyId?: number) {
  if (!journeyId) return "/dashboard";
  const base = `/dashboard/journeys/${journeyId}`;
  return segments[tab] ? `${base}/${segments[tab]}` : base;
}
export function tabFromPath(path: string): Tab {
  return (
    (Object.keys(segments) as Tab[]).find(
      (tab) => segments[tab] && path.endsWith(`/${segments[tab]}`),
    ) || "Dashboard"
  );
}
