'use client';

import DeviceCard from '@/components/DeviceCard';
import { useLiveState } from '@/hooks/useLiveState';

export default function Home() {
  const { state, connected, error } = useLiveState();

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">🌿 GrowHub</h1>
          <p className="text-sm text-slate-400">Tableau de bord temps réel</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              connected ? 'bg-emerald-400' : 'bg-slate-600'
            }`}
          />
          <span className="text-slate-300">
            {connected ? 'Flux en direct' : 'Reconnexion…'}
          </span>
        </div>
      </header>

      {error && (
        <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          {error}
        </div>
      )}

      {state && state.count === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center text-slate-400">
          <p className="text-lg">En attente de données…</p>
          <p className="mt-1 text-sm">
            Aucun appareil connecté pour le moment. Le Pico publie ses mesures
            toutes les 30 secondes.
          </p>
        </div>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
        {state?.devices.map((device) => (
          <DeviceCard key={device.id} device={device} />
        ))}
      </div>
    </main>
  );
}
