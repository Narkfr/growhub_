'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import DeviceCard from '@/components/DeviceCard';
import { useDevices } from '@/hooks/useDevices';
import { useLiveState, useSession } from '@/hooks/useLiveState';
import { findDevice } from '@/lib/display';

export default function Home() {
  const router = useRouter();
  const { user, loading: sessionLoading } = useSession();
  const { devices, loading, error } = useDevices();
  const { snapshot, connected, error: liveError } = useLiveState();

  useEffect(() => {
    if (!sessionLoading && user === null) router.replace('/login');
  }, [sessionLoading, user, router]);

  if (sessionLoading || loading || user === null) {
    return <main className="mx-auto max-w-5xl px-6 py-10 text-slate-400">Chargement…</main>;
  }

  const pending = devices.filter((device) => device.status === 'provisioning');

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">🌿 GrowHub</h1>
          <p className="text-sm text-slate-400">
            {devices.length} Bourgeon{devices.length > 1 ? 's' : ''} · {user.display_name || user.username}
          </p>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${connected ? 'bg-emerald-400' : 'bg-slate-600'}`}
            />
            <span className="text-slate-300">
              {connected ? 'Flux en direct' : 'Reconnexion…'}
            </span>
          </span>
          <Link
            href="/pair"
            className="rounded-lg bg-emerald-600 px-3 py-1.5 font-medium text-white"
          >
            Ajouter un Bourgeon
          </Link>
        </div>
      </header>

      {(error || liveError) && (
        <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          {error ?? liveError}
        </div>
      )}

      {pending.length > 0 && (
        <div className="mb-6 rounded-xl border border-slate-700 bg-slate-900/60 px-4 py-3 text-sm text-slate-300">
          {pending.length} boîtier{pending.length > 1 ? 's' : ''} flashé
          {pending.length > 1 ? 's' : ''} mais pas encore appairé
          {pending.length > 1 ? 's' : ''} : saisissez le code affiché sur l’écran via
          « Ajouter un Bourgeon ».
        </div>
      )}

      {devices.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center text-slate-400">
          <p className="text-lg">Aucun Bourgeon pour l’instant</p>
          <p className="mt-1 text-sm">
            Branchez un boîtier, puis saisissez le code affiché sur son écran.
          </p>
        </div>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2">
          {devices.map((device) => (
            <DeviceCard
              key={device.id}
              device={device}
              live={findDevice(snapshot?.devices ?? [], device.id)}
            />
          ))}
        </div>
      )}
    </main>
  );
}
