'use client';

import Link from 'next/link';

import type { Device, LiveDevice } from '@growhub/client';

import { actuatorState, humanize, isFresh, readings, statusLabel } from '@/lib/display';

function badgeClass(online: boolean): string {
  return online
    ? 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30'
    : 'bg-slate-500/15 text-slate-300 ring-slate-500/30';
}

export default function DeviceCard({ device, live }: { device: Device; live?: LiveDevice }) {
  const lines = readings(live);
  const fresh = live ? isFresh(live) : false;
  const state = live?.status ?? device.status;
  const online = state === 'online' && fresh;

  return (
    <Link
      href={`/devices/${device.id}`}
      className="block rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-sm transition hover:border-emerald-500/40"
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="break-all text-lg font-semibold">{device.name}</h2>
          <p className="text-xs text-slate-400">{device.device_id}</p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${badgeClass(online)}`}
        >
          {fresh ? statusLabel(state) : 'Sans nouvelles'}
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-3">
        {lines.map((line) => (
          <div
            key={`${line.source}-${line.metric}`}
            className="rounded-xl bg-slate-800/60 p-3"
          >
            <dt className="text-xs text-slate-400">{line.metricLabel}</dt>
            <dd className="mt-1 text-xl font-semibold tabular-nums">{line.text}</dd>
          </div>
        ))}
        {lines.length === 0 && (
          <p className="col-span-2 text-sm text-slate-500">Aucune mesure reçue.</p>
        )}
      </dl>

      {live && Object.keys(live.actuators).length > 0 && (
        <div className="mt-4 border-t border-slate-800 pt-4">
          <h3 className="mb-2 text-xs uppercase tracking-wide text-slate-400">
            Actionneurs
          </h3>
          <ul className="flex flex-wrap gap-2">
            {Object.entries(live.actuators).map(([id, value]) => (
              <li
                key={id}
                className={`rounded-full px-3 py-1 text-sm font-medium ${
                  value === 'ON'
                    ? 'bg-amber-500/15 text-amber-300'
                    : 'bg-slate-800 text-slate-400'
                }`}
              >
                {humanize(id)} · {actuatorState(value)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Link>
  );
}
