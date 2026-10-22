import { describe, expect, it } from 'vitest';
import { citationId, linkCitations } from './citations';
import { EventParser } from './sse';

describe('EventParser', () => {
  it('reassembles events split across network chunks', () => {
    const parser = new EventParser();
    expect(parser.feed('event: token\ndata: {"te')).toEqual([]);
    expect(parser.feed('xt": "Hi"}\n\nevent: done\ndata: {"reply": "Hi"}\n\n')).toEqual([
      { event: 'token', data: { text: 'Hi' } },
      { event: 'done', data: { reply: 'Hi' } },
    ]);
  });

  it('accepts CRLF line endings', () => {
    expect(new EventParser().feed('event: step\r\ndata: {"label": "x"}\r\n\r\n')).toEqual([{ event: 'step', data: { label: 'x' } }]);
  });
});

describe('linkCitations', () => {
  it('numbers known citations by first appearance and leaves unknown ones as text', () => {
    const { markdown, order } = linkCitations('A [p2-c0] B [p1-c1] C [p2-c0] D [p9-c9]', new Set(['p1-c1', 'p2-c0']));
    expect(order).toEqual(['p2-c0', 'p1-c1']);
    expect(markdown).toBe('A [1](#cite-p2-c0) B [2](#cite-p1-c1) C [1](#cite-p2-c0) D [p9-c9]');
    expect(citationId('#cite-p2-c0')).toBe('p2-c0');
    expect(citationId('https://example.com')).toBeNull();
  });
});
