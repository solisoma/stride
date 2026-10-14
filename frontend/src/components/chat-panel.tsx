'use client';
import { useEffect, useRef, type RefObject } from 'react';
import ReactMarkdown from 'react-markdown';
import { Sources } from './sources';
import type { ChatMessage } from '@/types/learning';

type Props = {
  open: boolean;
  onOpenChange: (value: boolean) => void;
  messages: ChatMessage[];
  message: string;
  onMessage: (value: string) => void;
  onSend: () => void;
  busy: boolean;
  hasMaterials: boolean;
  topic: string;
  contextLabel: string;
  inputRef: RefObject<HTMLTextAreaElement | null>;
};

export function ChatPanel({ open, onOpenChange, messages, message, onMessage, onSend, busy, hasMaterials, topic, contextLabel, inputRef }: Props) {
  const end = useRef<HTMLDivElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const panel = dialog.current;
    if (!panel) return;
    if (open && !panel.open) { panel.showModal(); inputRef.current?.focus(); }
    if (!open && panel.open) panel.close();
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previousOverflow; };
  }, [open, inputRef]);
  useEffect(() => { if (open) end.current?.scrollIntoView({ block: 'nearest' }); }, [messages.length, open]);
  return <>
    <button className="chat-launcher" type="button" aria-haspopup="dialog" aria-expanded={open} aria-controls="journey-chat" onClick={() => onOpenChange(true)}><span aria-hidden="true">✦</span> Ask your coach</button>
    <dialog ref={dialog} id="journey-chat" className="chat-dialog" aria-label="Your learning coach" onClose={() => onOpenChange(false)} onCancel={() => onOpenChange(false)} onClick={e => { if (e.target === e.currentTarget) onOpenChange(false); }}>
    <aside className="conversation-column" aria-label="Journey conversation">
    <div className="conversation-heading"><span className="coach-avatar">S</span><div><h2>Your learning coach</h2><span className="small">{contextLabel}</span></div><button className="chat-close" type="button" aria-label="Close chat" onClick={() => onOpenChange(false)}>×</button></div>
    <p>One conversation for this journey, across reading and practice.</p>
    <div className="chat-history">
      {!messages.length && <div className="conversation-empty"><span className="conversation-spark" aria-hidden="true">✦</span><h3>Let’s work through it.</h3><p>Ask about the guide, discuss your answer, or request a simpler explanation.</p><div className="suggested-prompts"><button type="button" disabled={busy} onClick={() => onMessage(topic ? `Explain ${topic} with a simple example.` : 'Help me understand the key concepts in my materials.')}>Explain with an example</button><button type="button" disabled={busy} onClick={() => onMessage(topic ? `What are common misconceptions about ${topic}?` : 'What should I focus on first?')}>What am I missing?</button></div></div>}
      {messages.map(m => <article key={m.id}><div className="chat-user"><strong>You</strong><p>{m.message}</p></div><div className="chat-coach"><strong>Stride</strong><ReactMarkdown>{m.content}</ReactMarkdown><Sources sources={m.sources} citations={m.citations}/><span className="small">Material revision {m.revision}{m.context ? ` · ${m.context.kind}: ${m.context.topic}` : ''}{m.context?.stale ? ' · Earlier guide; reply uses current materials' : ''}</span></div></article>)}
      <div ref={end}/>
    </div>
    <form className="chat-composer" onSubmit={e => { e.preventDefault(); onSend(); }}><label htmlFor="message">Your question</label><textarea ref={inputRef} id="message" disabled={busy} required rows={3} maxLength={10000} value={message} onChange={e => onMessage(e.target.value)} placeholder="Ask about what you’re reading or practising…"/><button disabled={busy || !message.trim() || !hasMaterials}>Send question →</button></form>
  </aside>
    </dialog>
  </>;
}
