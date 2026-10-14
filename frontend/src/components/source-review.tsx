'use client';
import { useState } from 'react';
import type { SourceReview as Review } from '@/types/learning';
import { Sources } from './sources';
export function SourceReview({ review, busy, onDecision }: { review: Review; busy: boolean; onDecision: (id: number, decision: string, note: string) => void }) {
  const [decision, setDecision] = useState(review.decision);
  const [note, setNote] = useState(review.note);
  return <article className="review-card"><h3>Compare the explanations</h3><div className="comparison"><div><h4>Your material says</h4><p>{review.source_claim}</p></div><div><h4>Possible alternative — unverified</h4><p>{review.alternative}</p></div></div><p>{review.reason}</p><p className="small">This is an AI-assisted concern, not a confirmed error. Your choice sets how to study it; it does not verify the claim.</p><Sources sources={review.sources} citations={review.citations}/><label htmlFor={`decision-${review.id}`}>How should we use this material?</label><select id={`decision-${review.id}`} value={decision} onChange={e => setDecision(e.target.value)}><option value="pending">Keep unresolved and explain both</option><option value="use_source">Follow my source for this journey</option><option value="use_alternative">Use the proposed interpretation (unverified)</option><option value="exclude">Exclude the cited passages</option></select><label htmlFor={`note-${review.id}`}>Your reasoning or correction (optional)</label><textarea id={`note-${review.id}`} rows={2} maxLength={3000} value={note} onChange={e => setNote(e.target.value)}/><button disabled={busy} onClick={() => onDecision(review.id, decision, note)}>Save my decision</button></article>;
}
