export interface ServerEvent {
  event: string;
  data: unknown;
}

/** Incremental text/event-stream parser: feed raw chunks, receive complete events. */
export class EventParser {
  private buffer = '';

  feed(chunk: string): ServerEvent[] {
    this.buffer += chunk.replace(/\r\n/g, '\n');
    const events: ServerEvent[] = [];
    let boundary: number;
    while ((boundary = this.buffer.indexOf('\n\n')) !== -1) {
      const block = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      let event = 'message';
      const data: string[] = [];
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
      }
      if (data.length) events.push({ event, data: JSON.parse(data.join('\n')) });
    }
    return events;
  }
}
