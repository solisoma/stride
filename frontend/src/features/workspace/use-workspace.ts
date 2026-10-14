"use client";
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useSession } from "@/hooks/use-session";
import { api } from "@/services/api";
import { downloadGuide } from "@/utils/download-guide";
import type {
  Goal,
  Guide,
  Question,
  Feedback,
  Progress,
  Plan,
  Material,
  ChatMessage,
  SourceReview as Review,
  SavedActivity,
  NextStep,
} from "@/types/learning";
import { tabFromPath, workspaceHref, type Tab } from "./config";

export function useWorkspaceController() {
  const auth = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const { user, journeys, ready } = auth;
  const routeJourneyId = pathname.match(
    /^\/dashboard\/journeys\/(\d+)(?:\/|$)/,
  )?.[1];
  const journey = routeJourneyId
    ? journeys.find((j) => String(j.id) === routeJourneyId) || null
    : null;
  const tab = tabFromPath(pathname);
  function setTab(value: Tab) {
    router.push(workspaceHref(value, journey?.id));
  }
  const session = {
    ...auth,
    select(value: typeof journey) {
      auth.select(value);
      router.push(
        value ? workspaceHref("Dashboard", value.id) : "/dashboard/new",
      );
    },
    async created(value: NonNullable<typeof journey>) {
      await auth.created(value);
      router.push(workspaceHref("Dashboard", value.id));
    },
    async logout() {
      await auth.logout();
      router.replace("/login");
    },
  };
  const [goal, setGoal] = useState<Goal>("exam");
  const [subject, setSubject] = useState("");
  const [busy, setBusy] = useState("");
  const [loadedJourneyId, setLoadedJourneyId] = useState<number | null>(null);
  const journeyLoading = Boolean(journey && loadedJourneyId !== journey.id);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [topic, setTopic] = useState("");
  const [format, setFormat] = useState("typed");
  const [files, setFiles] = useState<File[]>([]);
  const [guide, setGuide] = useState<Guide | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [activities, setActivities] = useState<SavedActivity[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [message, setMessage] = useState("");
  const [chatOpen, setChatOpen] = useState(false);
  const [legacy, setLegacy] = useState<{
    id: number;
    access_token: string;
  } | null>(null);
  const chatInput = useRef<HTMLTextAreaElement>(null);
  const submission = useRef("");
  const running = useRef(false);

  const pendingMaterials = materials.some(m => m.status === 'queued' || m.status === 'processing' || m.plan_pending);
  useEffect(() => {
    if (!journey || !pendingMaterials || !user) return;
    const selected = journey;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const documents = await api.documents(selected);
        if (cancelled) return;
        const pending = documents.some(m => m.status === 'queued' || m.status === 'processing' || m.plan_pending);
        if (!pending) {
          const [currentPlan, saved, chat, currentProgress, concerns] = await Promise.all([
            api.plan(selected), api.activities(selected), api.chatHistory(selected), api.progress(selected), api.reviews(selected),
          ]);
          if (cancelled) return;
          setPlan(currentPlan); setActivities(saved); setMessages(chat);
          setProgress(currentProgress); setReviews(concerns);
        }
        setMaterials(documents);
        if (!cancelled && pending) timer = setTimeout(poll, 2500);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Could not refresh processing status.');
          timer = setTimeout(poll, 5000);
        }
      }
    }
    timer = setTimeout(poll, 2000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [journey?.id, pendingMaterials, user?.id]);

  async function loadJourney() {
    if (!journey) return;
    const [documents, currentPlan, saved, chat, currentProgress, concerns] =
      await Promise.all([
        api.documents(journey),
        api.plan(journey),
        api.activities(journey),
        api.chatHistory(journey),
        api.progress(journey),
        api.reviews(journey),
      ]);
    setMaterials(documents);
    setPlan(currentPlan);
    setActivities(saved);
    setMessages(chat);
    setProgress(currentProgress);
    setReviews(concerns);
  }

  useEffect(() => {
    let cancelled = false;
    setLoadedJourneyId(null);
    setGuide(null);
    setQuestion(null);
    setFeedback(null);
    setTopic("");
    setAnswer("");
    setFiles([]);
    setError("");
    setNotice("");
    setPlan(null);
    setMaterials([]);
    setActivities([]);
    setMessages([]);
    setReviews([]);
    setProgress(null);
    setMessage("");
    setChatOpen(false);
    if (journey) {
      setBusy("Loading your saved journey…");
      Promise.all([
        api.documents(journey),
        api.plan(journey),
        api.activities(journey),
        api.chatHistory(journey),
        api.progress(journey),
        api.reviews(journey),
      ])
        .then(
          ([
            documents,
            currentPlan,
            saved,
            chat,
            currentProgress,
            concerns,
          ]) => {
            if (cancelled) return;
            setMaterials(documents);
            setPlan(currentPlan);
            setActivities(saved);
            setMessages(chat);
            setProgress(currentProgress);
            setReviews(concerns);
          },
        )
        .catch((e) => {
          if (!cancelled)
            setError(
              e instanceof Error ? e.message : "Could not load this journey.",
            );
        })
        .finally(() => {
          if (!cancelled) {
            setLoadedJourneyId(journey.id);
            setBusy("");
          }
        });
    } else setBusy("");
    return () => {
      cancelled = true;
    };
  }, [journey?.id, user?.id]);

  useEffect(() => {
    if (!user) {
      setLegacy(null);
      return;
    }
    try {
      const old = JSON.parse(
        localStorage.getItem("learnforward.journey") || "null",
      );
      if (
        old &&
        typeof old.id === "number" &&
        typeof old.access_token === "string"
      )
        setLegacy(old);
    } catch {
      /* No legacy journey */
    }
  }, [user?.id]);

  async function run(label: string, action: () => Promise<void>) {
    if (running.current) return;
    running.current = true;
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Something went wrong. Please retry.",
      );
    } finally {
      running.current = false;
      setBusy("");
    }
  }

  function follow(next: NextStep) {
    if (!next.topic) {
      setTab("Plan");
      return;
    }
    setTopic(next.topic);
    setTab(
      next.action === "study" || next.action === "revise_then_practise"
        ? "Study"
        : "Learn",
    );
    setGuide(null);
    setQuestion(null);
    setFeedback(null);
    setAnswer("");
  }

  function download() {
    if (guide) downloadGuide(guide);
  }

  async function newQuestion() {
    if (!journey) return;
    const next = await api.question(journey, topic.trim(), format);
    setQuestion(next);
    setAnswer("");
    setFeedback(null);
    submission.current = crypto.randomUUID();
    await loadJourney();
  }

  const next = feedback?.next || plan?.next;
  const activeTopics = plan?.topics.filter((t) => t.active) || [];
  const needsWork = activeTopics.filter((t) =>
    [
      "needs_revision",
      "needs_independent_check",
      "recheck_after_update",
      "clarification_needed",
    ].includes(t.status),
  );
  const dueTopics = activeTopics.filter((t) => t.due);
  return {
    session,
    user,
    journey,
    journeys,
    ready,
    journeyLoading,
    goal,
    setGoal,
    subject,
    setSubject,
    tab,
    setTab,
    busy,
    setBusy,
    error,
    setError,
    notice,
    setNotice,
    topic,
    setTopic,
    format,
    setFormat,
    files,
    setFiles,
    guide,
    setGuide,
    question,
    setQuestion,
    answer,
    setAnswer,
    feedback,
    setFeedback,
    progress,
    setProgress,
    plan,
    setPlan,
    materials,
    setMaterials,
    activities,
    setActivities,
    reviews,
    setReviews,
    messages,
    setMessages,
    message,
    setMessage,
    chatOpen,
    setChatOpen,
    legacy,
    setLegacy,
    chatInput,
    submission,
    loadJourney,
    run,
    follow,
    download,
    newQuestion,
    next,
    activeTopics,
    needsWork,
    dueTopics,
  };
}

export type WorkspaceState = ReturnType<typeof useWorkspaceController>;
