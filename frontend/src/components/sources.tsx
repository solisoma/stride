import type { Source } from '@/types/learning';
export function Sources({ sources, citations }: { sources: Source[]; citations: string[] }) {
  return <details className="sources"><summary>Check the sources</summary>{sources.filter(s => citations.includes(s.id)).map(s => <blockquote key={s.id}><strong>{s.document} · {s.timestamp || `Location ${s.page}`}</strong><p>{s.text}</p></blockquote>)}</details>;
}
