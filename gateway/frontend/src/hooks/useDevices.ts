'use client';

import { useCallback, useEffect, useState } from 'react';

import type { Device } from '@growhub/client';

import { apiClient } from '@/lib/client';
import { messageOf } from '@/hooks/useLiveState';

/**
 * Bourgeons dont l'utilisateur est membre.
 *
 * La liste vient de l'API (nom, rôle, partages) et l'état temps réel du flux :
 * les deux sont complémentaires, le flux ne porte que les mesures.
 */
export function useDevices() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setDevices(await apiClient().listDevices());
      setError(null);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { devices, loading, error, reload };
}
