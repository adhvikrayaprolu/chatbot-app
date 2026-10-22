import { METHOD_INFO, type Message, type Passage } from '../types';
import { Markdown } from './Markdown';

interface Props {
  message: Message;
  onOpenSource(documentId: string, passage: Passage): void;
}

export function MessageView({ message, onOpenSource }: Props) {
  if (message.role === 'user') {
    return <article className="message user"><p>{message.content}</p></article>;
  }
  const grounded = message.grounded;
  const steps = grounded?.steps ?? message.steps ?? [];
  const evidence = grounded?.evidence ?? message.evidence ?? [];
  const citations = grounded?.citations ?? [];
  const known = new Set((citations.length ? citations : evidence).map((p) => p.id));
  const byId = new Map([...evidence, ...citations].map((p) => [p.id, p]));
  const documentId = grounded?.document_id;
  const open = (id: string) => {
    const passage = byId.get(id);
    if (passage && documentId && !grounded?.source_removed) onOpenSource(documentId, passage);
  };

  return (
    <article className={`message assistant${message.error ? ' failed' : ''}`} aria-busy={message.pending}>
      {steps.length > 0 && (
        <details className="trace" open={message.pending}>
          <summary>
            {message.pending ? <span className="spinner" aria-hidden /> : null}
            {grounded ? `${METHOD_INFO[grounded.method]?.label ?? grounded.method} · ${steps.length} steps` : 'Searching…'}
          </summary>
          <ol>{steps.map((step, i) => <li key={i}>{step}</li>)}</ol>
        </details>
      )}
      {message.content
        ? <Markdown text={message.content} known={known} onCite={open} />
        : message.pending && <p className="muted"><span className="spinner" aria-hidden /> {evidence.length ? 'Writing answer…' : 'Thinking…'}</p>}
      {message.error && <p className="error" role="alert">{message.error}</p>}
      {grounded && citations.length > 0 && (
        <ul className="sources" aria-label="Sources">
          {citations.map((p, i) => (
            <li key={p.id}>
              <button type="button" onClick={() => open(p.id)} disabled={grounded.source_removed}>
                <span className="cite static">{i + 1}</span>
                <span className="source-label">{p.section || 'Passage'}</span>
                <span className="muted">p. {p.page}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {grounded?.source_removed && <p className="muted">Source removed; passage text is no longer available.</p>}
      {grounded && (
        <p className="stats">
          {grounded.seconds.toFixed(1)}s · {grounded.model_calls} model {grounded.model_calls === 1 ? 'call' : 'calls'} ·{' '}
          {(grounded.input_tokens + grounded.output_tokens).toLocaleString()} tokens
        </p>
      )}
    </article>
  );
}
