'use client';

import { useEffect, useState } from 'react';

import type { StatePayload } from '@/lib/types';

const POLL_INTERVAL_MS = 5000;

/**
 * Live device state: opens an SSE stream for instant updates and falls back
 * to polling when the stream drops (e.g. through a buffering proxy).
 */
export function useLiveState() {
  const [state, setState] = useState<StatePayload | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let es: EventSource | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;

    async function fetchState() {
      try {
        const res = await fetch('/api/state');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setState(await res.json());
        setError(null);
      } catch {
        setError("Impossible de joindre l'API.");
      }
    }

    fetchState();

    es = new EventSource('/api/stream');
    es.onopen = () => {
      setConnected(true);
      setError(null);
      if (poll) {
        clearInterval(poll);
        poll = null;
      }
    };
    es.onmessage = (event) => {
      try {
        setState(JSON.parse(event.data));
      } catch {
        /* ignore malformed frame */
      }
    };
    es.onerror = () => {
      setConnected(false);
      if (!poll) {
        poll = setInterval(fetchState, POLL_INTERVAL_MS);
      }
    };

    return () => {
      es?.close();
      if (poll) clearInterval(poll);
    };
  }, []);

  return { state, connected, error };
}
