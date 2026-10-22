const CITATION = /\[(p\d+-c\d+)\]/g;

/**
 * Replace `[p12-c0]` markers with numbered Markdown links that the renderer turns into
 * citation chips. Numbers follow first appearance; unknown IDs are left as plain text.
 */
export function linkCitations(text: string, known: Set<string>): { markdown: string; order: string[] } {
  const order: string[] = [];
  const markdown = text.replace(CITATION, (match, id: string) => {
    if (!known.has(id)) return match;
    if (!order.includes(id)) order.push(id);
    return `[${order.indexOf(id) + 1}](#cite-${id})`;
  });
  return { markdown, order };
}

export function citationId(href: string | undefined): string | null {
  return href?.startsWith('#cite-') ? href.slice(6) : null;
}
