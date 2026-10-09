'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import type { Device } from '@growhub/client';

import { apiClient } from '@/lib/client';
import { messageOf } from '@/hooks/useLiveState';

/**
 * Appairage : l'utilisateur saisit le code affiché sur l'écran du boîtier.
 *
 * Le boîtier n'est jamais « ajouté » à la main : c'est ce code, à usage unique
 * et à durée limitée, qui prouve qu'on a le boîtier sous les yeux.
 */
export default function PairPage() {
  const router = useRouter();
  const [code, setCode] = useState('');
  const [device, setDevice] = useState<Device | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await apiClient().redeemClaim(code.trim().toUpperCase());
      setDevice(result.device);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-md px-6 py-12">
      <Link href="/" className="text-sm text-slate-400 hover:underline">
        ← Retour
      </Link>
      <h1 className="mb-1 mt-4 text-2xl font-bold">Ajouter un Bourgeon</h1>
      <p className="mb-8 text-sm text-slate-400">
        Le code s’affiche sur l’écran du boîtier une fois allumé.
      </p>

      {device ? (
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-5">
          <p className="font-medium text-emerald-200">
            « {device.name} » est appairé.
          </p>
          <p className="mt-1 text-sm text-slate-300">
            Le boîtier reçoit ses identifiants définitifs et redémarre : ses mesures
            apparaîtront d’ici une minute.
          </p>
          <button
            type="button"
            onClick={() => router.push(`/devices/${device.id}`)}
            className="mt-4 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white"
          >
            Ouvrir le tableau de bord
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <label className="block text-sm text-slate-300">
            Code d’appairage
            <input
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="ABC234"
              autoCapitalize="characters"
              required
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-center text-xl tracking-[0.3em] text-slate-100"
            />
          </label>

          {error && (
            <p role="alert" className="text-sm text-rose-300">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-emerald-600 py-2 font-medium text-white disabled:opacity-50"
          >
            {busy ? 'Appairage…' : 'Appairer'}
          </button>
          <p className="text-xs text-slate-500">
            Un code est à usage unique et expire : s’il est refusé, régénérez-en un
            avec <code>provision_device --force</code>.
          </p>
        </form>
      )}
    </main>
  );
}
