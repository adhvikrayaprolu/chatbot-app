import { useRef } from 'react';
import type { ConversationSummary, DocumentInfo } from '../types';

interface Props {
  open: boolean;
  conversations: ConversationSummary[];
  currentId: string | null;
  documents: DocumentInfo[];
  busy: boolean;
  onClose(): void;
  onSaved(): void;
  onSelect(id: string): void;
  onNew(): void;
  onImport(file: File): void;
  onDemo(): void;
  onRetry(id: string): void;
  onRemove(doc: DocumentInfo): void;
}

function progress(doc: DocumentInfo) {
  const count = (n: number | undefined, noun: string) => `${n ?? '?'} ${noun}${n === 1 ? '' : 's'}`;
  if (doc.status === 'ready') return `${count(doc.metadata.pages, 'page')} · ${count(doc.metadata.chunks, 'passage')}`;
  if (doc.status === 'failed') return doc.error ?? 'Import failed';
  if (doc.status === 'indexing' && doc.metadata.chunks)
    return `Embedding ${doc.metadata.embedded ?? 0} / ${doc.metadata.chunks} passages`;
  return doc.status === 'queued' ? 'Queued' : 'Reading PDF…';
}

export function Sidebar(props: Props) {
  const file = useRef<HTMLInputElement>(null);
  return (
    <aside className={`sidebar${props.open ? ' open' : ''}`} aria-label="Conversations and library">
      <div className="brand">
        <span className="logo" aria-hidden>◆</span>
        <span>Document Intelligence</span>
        <button type="button" className="icon close-sidebar" aria-label="Close menu" onClick={props.onClose}>×</button>
      </div>
      <button type="button" className="primary block" onClick={props.onNew} disabled={props.busy}>+ New chat</button>
      <nav aria-label="Saved conversations" className="conversations">
        {props.conversations.length === 0 && <p className="muted small">No conversations yet.</p>}
        {props.conversations.map((c) => (
          <button key={c.id} type="button" aria-current={c.id === props.currentId ? 'page' : undefined}
            onClick={() => props.onSelect(c.id)}>{c.title}</button>
        ))}
      </nav>
      <section className="library" aria-labelledby="library-heading">
        <h2 id="library-heading">Library</h2>
        <ul>
          {props.documents.map((doc) => (
            <li key={doc.id} className={`doc ${doc.status}`}>
              <div>
                <strong title={doc.title}>{doc.title}</strong>
                <span className="small muted" role="status">{progress(doc)}</span>
              </div>
              <div className="doc-actions">
                {doc.status === 'failed' && <button type="button" className="link" onClick={() => props.onRetry(doc.id)}>Retry</button>}
                {(doc.status === 'ready' || doc.status === 'failed') && (
                  <button type="button" className="link" aria-label={`Remove ${doc.title}`} onClick={() => props.onRemove(doc)}>Remove</button>
                )}
              </div>
            </li>
          ))}
        </ul>
        <input ref={file} id="pdf-file" type="file" accept="application/pdf" className="visually-hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) props.onImport(f); e.target.value = ''; }} />
        <div className="library-actions">
          <button type="button" onClick={() => file.current?.click()}>Import PDF</button>
          <button type="button" className="ghost" onClick={props.onDemo}>Try GPU demo notes</button>
        </div>
        <button type="button" className="link saved" onClick={props.onSaved}>Saved method comparisons →</button>
      </section>
    </aside>
  );
}
