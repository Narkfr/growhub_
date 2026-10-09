/**
 * Minimal Server-Sent Events parser.
 *
 * Kept pure (a string in, events and leftover out) so it can be tested without a
 * network, and so the same code serves the browser build and a mobile build
 * where no `EventSource` exists.
 */

export interface SseEvent {
  /** `event:` field of the frame; `message` when the server omits it. */
  event: string;
  /** Concatenated `data:` lines of the frame. */
  data: string;
}

export interface SseParseResult {
  events: SseEvent[];
  /** Incomplete tail, to be prepended to the next network chunk. */
  rest: string;
}

const FRAME_SEPARATOR = /\r?\n\r?\n/;

export function parseSseChunk(buffer: string): SseParseResult {
  const frames = buffer.split(FRAME_SEPARATOR);
  const rest = frames.pop() ?? '';
  const events: SseEvent[] = [];

  for (const frame of frames) {
    const data: string[] = [];
    let event = 'message';
    for (const line of frame.split(/\r?\n/)) {
      if (line.startsWith(':')) continue; // commentaire / keep-alive
      const separator = line.indexOf(':');
      const field = separator === -1 ? line : line.slice(0, separator);
      const value = separator === -1 ? '' : line.slice(separator + 1).replace(/^ /, '');
      if (field === 'data') data.push(value);
      else if (field === 'event') event = value;
    }
    // Une trame sans champ `data` n'est pas un événement (commentaire,
    // keep-alive, `event:` isolé) : la spec SSE ne la dispatche pas.
    if (data.length > 0) {
      events.push({ event, data: data.join('\n') });
    }
  }

  return { events, rest };
}

/** Parses a `data: {...}` frame; returns null when the payload is not JSON. */
export function parseSseJson<T>(event: SseEvent): T | null {
  try {
    return JSON.parse(event.data) as T;
  } catch {
    return null;
  }
}
