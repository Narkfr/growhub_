import { describe, expect, it } from 'vitest';

import { parseSseChunk, parseSseJson } from './sse';

describe('parseSseChunk', () => {
  it('reads a complete frame', () => {
    const { events, rest } = parseSseChunk('data: {"count":1}\n\n');
    expect(rest).toBe('');
    expect(events).toEqual([{ event: 'message', data: '{"count":1}' }]);
  });

  it('keeps an incomplete tail for the next chunk', () => {
    const { events, rest } = parseSseChunk('data: {"cou');
    expect(events).toEqual([]);
    expect(rest).toBe('data: {"cou');
  });

  it('reassembles a frame split across two chunks', () => {
    const first = parseSseChunk('data: {"count":');
    const second = parseSseChunk(`${first.rest}2}\n\n`);
    expect(parseSseJson<{ count: number }>(second.events[0])).toEqual({ count: 2 });
  });

  it('handles several frames in one chunk', () => {
    const { events } = parseSseChunk('data: {"count":1}\n\ndata: {"count":2}\n\n');
    expect(events.map((event) => event.data)).toEqual(['{"count":1}', '{"count":2}']);
  });

  it('ignores keep-alive comments', () => {
    const { events } = parseSseChunk(': keep-alive\n\ndata: {"count":1}\n\n');
    expect(events).toEqual([{ event: 'message', data: '{"count":1}' }]);
  });

  it('supports CRLF frames', () => {
    const { events, rest } = parseSseChunk('data: {"count":1}\r\n\r\n');
    expect(rest).toBe('');
    expect(events).toEqual([{ event: 'message', data: '{"count":1}' }]);
  });

  it('reads the event name', () => {
    const { events } = parseSseChunk('event: devices\ndata: {"count":1}\n\n');
    expect(events[0].event).toBe('devices');
  });

  it('joins multi-line data', () => {
    const { events } = parseSseChunk('data: {"count":\ndata: 1}\n\n');
    expect(events[0].data).toBe('{"count":\n1}');
  });
});

describe('parseSseJson', () => {
  it('returns null instead of throwing on a malformed payload', () => {
    expect(parseSseJson({ event: 'message', data: 'pas du json' })).toBeNull();
  });

  it('parses an object payload', () => {
    expect(parseSseJson({ event: 'message', data: '{"count":3}' })).toEqual({ count: 3 });
  });
});
