'use client';
import { useState } from 'react';
import { api } from '@/services/api';
import type { User } from '@/types/learning';
export function AccountForm({ onAccount }: { onAccount: (user: User) => Promise<void> }) {
  const [register, setRegister] = useState(false);
  const [admin, setAdmin] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <section className="panel"><h2>{register ? 'Create your learning account' : admin ? 'Admin sign in' : 'Welcome back'}</h2><p>Your journeys, conversations, and progress stay with your account.</p><form onSubmit={async e => { e.preventDefault(); setBusy(true); setError(''); try { const user = register ? await api.register(name.trim(), email, password) : admin ? await api.adminLogin(email, password) : await api.login(email, password); await onAccount(user); } catch (e) { setError(e instanceof Error ? e.message : 'Please try again.'); } finally { setBusy(false); } }}>{register && <><label htmlFor="name">Name</label><input id="name" required maxLength={100} autoComplete="name" value={name} onChange={e => setName(e.target.value)}/></>}<label htmlFor="email">Email</label><input id="email" type="email" required autoComplete="email" value={email} onChange={e => setEmail(e.target.value)}/><label htmlFor="password">Password{register ? ' (at least 15 characters)' : ''}</label><input id="password" type="password" required minLength={register ? 15 : 1} maxLength={128} autoComplete={register ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)}/><button disabled={busy}>{busy ? 'Please wait…' : register ? 'Create account' : 'Sign in'}</button></form>{error && <p className="error" role="alert">{error}</p>}<button className="text-button" disabled={busy} onClick={() => { setRegister(!register); setAdmin(false); setError(''); }}>{register ? 'Already have an account? Sign in' : 'New here? Create an account'}</button>{!register && <button className="text-button" disabled={busy} onClick={() => { setAdmin(!admin); setError(''); }}>{admin ? 'Learner sign in' : 'Admin sign in'}</button>}</section>;
}
