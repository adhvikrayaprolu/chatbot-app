import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { citationId, linkCitations } from '../citations';

interface Props {
  text: string;
  known: Set<string>;
  onCite?: (id: string) => void;
}

/** Safe Markdown (no raw HTML) with `[p12-c0]` citation markers rendered as numbered chips. */
export function Markdown({ text, known, onCite }: Props) {
  const { markdown, order } = linkCitations(text, known);
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            const id = citationId(href);
            if (id) {
              return (
                <button type="button" className="cite" title={`Open source ${id}`} aria-label={`Source ${order.indexOf(id) + 1}: ${id}`}
                  onClick={() => onCite?.(id)}>
                  {children}
                </button>
              );
            }
            return <a href={href} target="_blank" rel="noreferrer noopener">{children}</a>;
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
