'use client';
import { useEffect, useState } from 'react';
import { api } from '@/services/api';
import type { Journey, User } from '@/types/learning';

export function useSession() {
  const [user, setUser] = useState<User | null>(null);
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [journey, setJourney] = useState<Journey | null>(null);
  const [ready, setReady] = useState(false);
  async function load(account: User) {
    const list = await api.journeys();
    setUser(account); setJourneys(list);
    let selected: string | null = null;
    try { selected = localStorage.getItem(`learnforward.selected.${account.id}`); } catch { /* session still works */ }
    setJourney(list.find(j => String(j.id) === selected) || list[0] || null);
  }
  useEffect(() => {
    let cancelled = false;
    async function resume() {
      try { const account = await api.me(); if (!cancelled) await load(account); }
      catch { if (!cancelled) setUser(null); }
      finally { if (!cancelled) setReady(true); }
    }
    void resume();
    return () => { cancelled = true; };
  }, []);
  function select(j: Journey | null) {
    setJourney(j);
    if (user) try { if (j) localStorage.setItem(`learnforward.selected.${user.id}`, String(j.id)); } catch { /* session still works */ }
  }
  async function created(j: Journey) {
    setJourneys(await api.journeys()); select(j);
  }
  async function logout() {
    await api.logout(); setUser(null); setJourneys([]); setJourney(null);
  }
  return { user, journeys, journey, ready, load, select, created, logout };
}
