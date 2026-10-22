import { METHOD_INFO, type ComparisonResult, type Method, type Passage } from '../types';
import { Markdown } from './Markdown';

interface Props {
  result: ComparisonResult;
  onOpenSource(documentId: string, passage: Passage): void;
}

const order = Object.keys(METHOD_INFO);

export function CompareView({ result, onOpenSource }: Props) {
  return (
    <div className="compare">
      <p className="compare-question">“{result.question}”</p>
      <div className="compare-grid">
        {Object.entries(result.results).sort(([a], [b]) => order.indexOf(a) - order.indexOf(b)).map(([method, answer]) => (
          <section key={method} className="compare-card" aria-label={METHOD_INFO[method as Method]?.label ?? method}>
            <h3>{METHOD_INFO[method as Method]?.label ?? method}</h3>
            {answer.status === 'failed' ? <p className="error">{answer.error}</p> : (
              <>
                <p className="stats">
                  {answer.seconds.toFixed(1)}s · {answer.model_calls} calls · {(answer.input_tokens + answer.output_tokens).toLocaleString()} tokens
                </p>
                <Markdown text={answer.reply} known={new Set(answer.citations.map((c) => c.id))}
                  onCite={(id) => { const p = answer.citations.find((c) => c.id === id); if (p) onOpenSource(result.document_id, p); }} />
                <details className="trace">
                  <summary>{answer.steps.length} steps · pages {[...new Set(answer.evidence.map((e) => e.page))].join(', ') || '—'}</summary>
                  <ol>{answer.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
                </details>
              </>
            )}
          </section>
        ))}
      </div>
      <p className="small muted">Comparisons are saved separately and never added to your chat history.</p>
    </div>
  );
}
