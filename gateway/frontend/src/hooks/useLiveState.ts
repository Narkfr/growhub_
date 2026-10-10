'use client';

import { useEffect, useState } from 'react';

import type { LiveSnapshot, User } from '@growhub/client';
import { GrowHubError } from '@growhub/client';

import { apiClient } from '@/lib/client';
import { noteServerClock } from '@/lib/display';

/** Message affichable pour n'importe quelle erreur remontée par le client. */
export function messageOf(error: unknown): string {
  if (error instanceof GrowHubError) return error.message;
  return "Impossible de joindre l'API.";
}

/**
 * État temps réel de tous les Bourgeons visibles par l'utilisateur.
 *
 * Le client partagé choisit le transport : flux SSE dans le navigateur
 * (rafraîchissement serveur toutes les 2 s), sondage ailleurs. L'écran ne sait
 * pas lequel est utilisé, et n'a donc rien à changer pour le mobile.
 */
export function useLiveState() {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return apiClient().subscribeLive(
      (next) => {
        // L'horloge du serveur arrive avec chaque instantané : c'est elle qui fait
        // foi pour juger la fraîcheur des mesures, pas celle de la machine qui
        // regarde l'écran.
        noteServerClock(next.now);
        setSnapshot(next);
        setConnected(true);
        setError(null);
      },
      (caught) => {
        setConnected(false);
        setError(messageOf(caught));
      },
    );
  }, []);

  return { snapshot, connected, error };
}

/** Profil courant, ou `null` : une session expirée renvoie sur /login. */
export function useSession() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiClient()
      .me()
      .then((profile) => {
        if (!cancelled) setUser(profile);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { user, loading };
}
