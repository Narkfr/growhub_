'use client';

import type { Device } from '@/lib/types';
import { actuatorLabel, flattenReadings, formatValue } from '@/lib/format';

function statusBadge(status: Device['status']) {
  if (status === 'online') {
    return {
      label: 'En ligne',
      cls: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
    };
  }
  if (status === 'offline') {
    return {
      label: 'Hors ligne',
      cls: 'bg-rose-500/15 text-rose-300 ring-rose-500/30',
    };
  }
  return {
    label: 'Inconnu',
    cls: 'bg-slate-500/15 text-slate-300 ring-slate-500/30',
  };
}

function lastSeen(timestamp: number | null): string {
  if (timestamp === null) return '—';
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - timestamp));
  if (seconds < 60) return `il y a ${seconds} s`;
  if (seconds < 3600) return `il y a ${Math.round(seconds / 60)} min`;
  return `il y a ${Math.round(seconds / 3600)} h`;
}

export default function DeviceCard({ device }: { device: Device }) {
  const badge = statusBadge(device.status);
  const readings = flattenReadings(device);

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="break-all text-lg font-semibold">{device.id}</h2>
          <p className="text-xs text-slate-400">
            Dernière donnée : {lastSeen(device.last_seen)}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${badge.cls}`}
        >
          {badge.label}
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-3">
        {readings.map((r) => (
          <div
            key={`${r.sensorId}-${r.metric}`}
            className="rounded-xl bg-slate-800/60 p-3"
          >
            <dt className="text-xs text-slate-400">{r.metricLabel}</dt>
            <dd className="mt-1 text-xl font-semibold tabular-nums">
              {formatValue(r.value, r.unit)}
            </dd>
          </div>
        ))}
        {readings.length === 0 && (
          <p className="col-span-2 text-sm text-slate-500">Aucune mesure reçue.</p>
        )}
      </dl>

      {Object.keys(device.actuators).length > 0 && (
        <div className="mt-4 border-t border-slate-800 pt-4">
          <h3 className="mb-2 text-xs uppercase tracking-wide text-slate-400">
            Actionneurs
          </h3>
          <ul className="flex flex-wrap gap-2">
            {Object.entries(device.actuators).map(([id, state]) => (
              <li
                key={id}
                className={`rounded-full px-3 py-1 text-sm font-medium ${
                  state === 'ON'
                    ? 'bg-amber-500/15 text-amber-300'
                    : 'bg-slate-800 text-slate-400'
                }`}
              >
                {actuatorLabel(id)} · {state === 'ON' ? 'ON' : 'OFF'}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
