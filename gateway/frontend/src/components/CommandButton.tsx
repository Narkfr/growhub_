'use client';

import { useState } from 'react';

import type { CommandKind } from '@growhub/client';

import { apiClient } from '@/lib/client';
import { actionLabel } from '@/lib/display';
import { messageOf } from '@/hooks/useLiveState';

interface Props {
  deviceId: number;
  kind: CommandKind;
  action: string;
  args?: Record<string, unknown>;
  className?: string;
}

/**
 * Envoie une commande et rend compte de son sort.
 *
 * Une commande part en asynchrone : le serveur la journalise, le Bourgeon
 * l'exécute puis acquitte. Ce bouton signale donc l'envoi, pas l'exécution —
 * l'état réel arrive par le flux temps réel, ce qui évite d'afficher un
 * succès que le boîtier n'a pas confirmé.
 */
export default function CommandButton({ deviceId, kind, action, args = {}, className }: Props) {
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);

  async function send() {
    setBusy(true);
    setFeedback(null);
    try {
      const audit = await apiClient().sendCommand(deviceId, kind, action, args);
      setFeedback({
        ok: true,
        text: audit.status === 'acked' ? 'Confirmé par le Bourgeon' : 'Commande envoyée',
      });
    } catch (error) {
      setFeedback({ ok: false, text: messageOf(error) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col gap-1">
      <button
        type="button"
        onClick={send}
        disabled={busy}
        className={
          className ??
          'rounded-lg border border-slate-700 px-3 py-1.5 text-sm transition hover:border-emerald-500/50 hover:text-emerald-300 disabled:opacity-50'
        }
      >
        {busy ? '…' : actionLabel(action)}
      </button>
      {feedback && (
        <span
          className={`text-xs ${feedback.ok ? 'text-emerald-300' : 'text-rose-300'}`}
          role="status"
        >
          {feedback.text}
        </span>
      )}
    </span>
  );
}
