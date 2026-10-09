'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import type { Device, TelemetryPoint } from '@growhub/client';

import CommandButton from '@/components/CommandButton';
import MembersPanel from '@/components/MembersPanel';
import { apiClient } from '@/lib/client';
import { useLiveState, messageOf } from '@/hooks/useLiveState';
import {
  actuatorActions,
  actuatorState,
  findDevice,
  humanize,
  isFresh,
  readings,
  statusLabel,
} from '@/lib/display';

export default function DevicePage() {
  const params = useParams<{ id: string }>();
  const deviceId = params.id;

  const [device, setDevice] = useState<Device | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [intervalSeconds, setIntervalSeconds] = useState('30');
  const [points, setPoints] = useState<TelemetryPoint[]>([]);
  const [metric, setMetric] = useState('');
  const [configFeedback, setConfigFeedback] = useState<string | null>(null);

  const { snapshot } = useLiveState();
  const live = findDevice(snapshot?.devices ?? [], Number(deviceId));

  useEffect(() => {
    apiClient()
      .getDevice(deviceId)
      .then(setDevice)
      .catch((caught) => setError(messageOf(caught)));
  }, [deviceId]);

  const loadHistory = useCallback(async () => {
    try {
      const history = await apiClient().telemetry(deviceId, {
        metric: metric || undefined,
        limit: 30,
      });
      setPoints(history.points);
    } catch (caught) {
      setError(messageOf(caught));
    }
  }, [deviceId, metric]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  async function applyInterval(event: React.FormEvent) {
    event.preventDefault();
    setConfigFeedback(null);
    try {
      await apiClient().sendCommand(deviceId, 'config', 'set', {
        telemetry_interval: Number(intervalSeconds),
      });
      setConfigFeedback('Configuration envoyée au Bourgeon.');
    } catch (caught) {
      setConfigFeedback(messageOf(caught));
    }
  }

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <Link href="/" className="text-sm text-slate-400 hover:underline">
          ← Mes Bourgeons
        </Link>
        <p className="mt-6 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-rose-200">
          {error}
        </p>
      </main>
    );
  }

  if (!device) {
    return <main className="mx-auto max-w-3xl px-6 py-10 text-slate-400">Chargement…</main>;
  }

  const lines = readings(live);
  const fresh = live ? isFresh(live) : false;
  const metrics = Array.from(
    new Set(lines.map((line) => line.metric)),
  );

  return (
    <main className="mx-auto max-w-3xl space-y-6 px-6 py-10">
      <div>
        <Link href="/" className="text-sm text-slate-400 hover:underline">
          ← Mes Bourgeons
        </Link>
        <div className="mt-4 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">{device.name}</h1>
            <p className="text-xs text-slate-500">
              {device.device_id} · {device.model} · firmware{' '}
              {device.fw_version || 'inconnu'}
            </p>
          </div>
          <span className="rounded-full bg-slate-800 px-3 py-1 text-xs">
            {fresh ? statusLabel(live?.status ?? device.status) : 'Sans nouvelles'}
          </span>
        </div>
      </div>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <h2 className="mb-3 font-semibold">Mesures</h2>
        {lines.length === 0 ? (
          <p className="text-sm text-slate-500">
            Aucune mesure pour l’instant. Le Bourgeon publie à intervalle régulier
            (30 secondes par défaut).
          </p>
        ) : (
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {lines.map((line) => (
              <div key={`${line.source}-${line.metric}`} className="rounded-xl bg-slate-800/60 p-3">
                <dt className="text-xs text-slate-400">
                  {line.metricLabel}
                  <span className="block text-[10px] text-slate-500">{line.sourceLabel}</span>
                </dt>
                <dd className="mt-1 text-xl font-semibold tabular-nums">{line.text}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <h2 className="mb-3 font-semibold">Actionneurs</h2>
        {Object.keys(live?.actuators ?? {}).length === 0 ? (
          <p className="text-sm text-slate-500">Aucun actionneur connu.</p>
        ) : (
          <ul className="space-y-3">
            {Object.entries(live?.actuators ?? {}).map(([name, value]) => (
              <li key={name} className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-sm">
                  {humanize(name)}{' '}
                  <strong
                    className={value === 'ON' ? 'text-amber-300' : 'text-slate-400'}
                  >
                    {actuatorState(value)}
                  </strong>
                </span>
                <span className="flex gap-2">
                  {actuatorActions().map((action) => (
                    <CommandButton
                      key={action}
                      deviceId={device.id}
                      kind="actuators"
                      action={action}
                      args={{ target: name }}
                    />
                  ))}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {device.role === 'owner' && (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
          <h2 className="mb-1 font-semibold">Configuration</h2>
          <p className="mb-3 text-xs text-slate-500">
            Le boîtier refuse un intervalle sous 5 secondes : c’est lui qui borne, pas
            l’interface.
          </p>
          <form onSubmit={applyInterval} className="flex items-end gap-2">
            <label className="text-xs text-slate-400">
              Intervalle de télémétrie (s)
              <input
                type="number"
                min={5}
                value={intervalSeconds}
                onChange={(event) => setIntervalSeconds(event.target.value)}
                className="mt-1 w-28 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100"
              />
            </label>
            <CommandButton
              deviceId={device.id}
              kind="config"
              action="set"
              args={{ telemetry_interval: Number(intervalSeconds) }}
            />
          </form>
          {configFeedback && (
            <p className="mt-3 text-xs text-slate-300">{configFeedback}</p>
          )}
        </section>
      )}

      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">Historique</h2>
          <select
            value={metric}
            onChange={(event) => setMetric(event.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-100"
          >
            <option value="">Toutes les mesures</option>
            {metrics.map((name) => (
              <option key={name} value={name}>
                {humanize(name)}
              </option>
            ))}
          </select>
        </div>
        {points.length === 0 ? (
          <p className="text-sm text-slate-500">Rien à afficher pour l’instant.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="pb-2">Quand</th>
                <th className="pb-2">Mesure</th>
                <th className="pb-2 text-right">Valeur</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {points.map((point) => (
                <tr key={point.id} className="border-t border-slate-800">
                  <td className="py-1.5 text-slate-400">
                    {new Date(point.ts).toLocaleString('fr-FR')}
                  </td>
                  <td className="py-1.5">
                    {humanize(point.source)} · {humanize(point.metric)}
                  </td>
                  <td className="py-1.5 text-right">
                    {point.value ?? '—'} {point.unit ?? ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <MembersPanel device={device} />
    </main>
  );
}
