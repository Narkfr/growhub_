'use client';

import { useCallback, useEffect, useState } from 'react';

import type { Device, Membership, Role } from '@growhub/client';

import { apiClient } from '@/lib/client';
import { messageOf } from '@/hooks/useLiveState';

const ROLE_LABELS: Record<Role, string> = {
  owner: 'Propriétaire',
  member: 'Membre',
  viewer: 'Lecture seule',
};

/**
 * Partage d'un Bourgeon : membres, ajout, retrait et cession.
 *
 * Seul le propriétaire voit ces commandes — le serveur refuse les autres de
 * toute façon, mais l'interface ne propose pas ce qu'elle ne peut pas obtenir.
 */
export default function MembersPanel({ device }: { device: Device }) {
  const [members, setMembers] = useState<Membership[]>([]);
  const [username, setUsername] = useState('');
  const [role, setRole] = useState<Role>('member');
  const [keepAccess, setKeepAccess] = useState(true);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const isOwner = device.role === 'owner';

  const load = useCallback(async () => {
    try {
      setMembers(await apiClient().listMembers(device.id));
    } catch (error) {
      setFeedback({ ok: false, text: messageOf(error) });
    }
  }, [device.id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFeedback(null);
    try {
      await apiClient().addMember(device.id, username, role);
      setUsername('');
      setFeedback({ ok: true, text: 'Membre ajouté.' });
      await load();
    } catch (error) {
      setFeedback({ ok: false, text: messageOf(error) });
    } finally {
      setBusy(false);
    }
  }

  async function remove(member: Membership) {
    setBusy(true);
    setFeedback(null);
    try {
      await apiClient().removeMember(device.id, member.user);
      setFeedback({ ok: true, text: 'Membre retiré.' });
      await load();
    } catch (error) {
      setFeedback({ ok: false, text: messageOf(error) });
    } finally {
      setBusy(false);
    }
  }

  async function transfer(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFeedback(null);
    try {
      await apiClient().transfer(device.id, username, keepAccess);
      setUsername('');
      setFeedback({
        ok: true,
        text: keepAccess
          ? 'Bourgeon cédé. Vous gardez un accès en lecture.'
          : "Bourgeon cédé. Vous n'y avez plus accès.",
      });
      await load();
    } catch (error) {
      setFeedback({ ok: false, text: messageOf(error) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="mb-3 font-semibold">Partage</h2>

      <ul className="mb-4 space-y-2 text-sm">
        {members.map((member) => (
          <li
            key={member.id}
            className="flex items-center justify-between rounded-lg bg-slate-950/60 px-3 py-2"
          >
            <span>
              {member.user_label || member.username}{' '}
              <span className="text-xs text-slate-500">{ROLE_LABELS[member.role]}</span>
            </span>
            {isOwner && member.role !== 'owner' && (
              <button
                type="button"
                onClick={() => void remove(member)}
                disabled={busy}
                className="text-xs text-rose-300 hover:underline disabled:opacity-50"
              >
                Retirer
              </button>
            )}
          </li>
        ))}
        {members.length === 0 && <li className="text-slate-500">Chargement…</li>}
      </ul>

      {isOwner ? (
        <>
          <form onSubmit={add} className="flex flex-wrap items-end gap-2">
            <label className="flex-1 text-xs text-slate-400">
              Nom d’utilisateur
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100"
              />
            </label>
            <label className="text-xs text-slate-400">
              Rôle
              <select
                value={role}
                onChange={(event) => setRole(event.target.value as Role)}
                className="mt-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100"
              >
                <option value="member">Membre</option>
                <option value="viewer">Lecture seule</option>
              </select>
            </label>
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              Ajouter
            </button>
          </form>

          <form onSubmit={transfer} className="mt-5 border-t border-slate-800 pt-4">
            <p className="text-sm text-slate-300">Céder ce Bourgeon</p>
            <p className="mt-1 text-xs text-slate-500">
              Les topics et l’historique restent attachés au boîtier : seule la propriété
              change de main.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Nom d’utilisateur"
                required
                className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100"
              />
              <label className="flex items-center gap-2 text-xs text-slate-400">
                <input
                  type="checkbox"
                  checked={keepAccess}
                  onChange={(event) => setKeepAccess(event.target.checked)}
                />
                Rester en lecture
              </label>
              <button
                type="submit"
                disabled={busy}
                className="rounded-lg border border-amber-500/50 px-3 py-1.5 text-sm text-amber-200 disabled:opacity-50"
              >
                Céder
              </button>
            </div>
          </form>
        </>
      ) : (
        <p className="text-xs text-slate-500">
          Seul le propriétaire peut ajouter des membres ou céder le Bourgeon.
        </p>
      )}

      {feedback && (
        <p
          role="status"
          className={`mt-3 text-xs ${feedback.ok ? 'text-emerald-300' : 'text-rose-300'}`}
        >
          {feedback.text}
        </p>
      )}
    </section>
  );
}
