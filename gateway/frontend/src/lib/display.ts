import type { LiveDevice, Metric } from '@growhub/client';

/** Ce qu'une carte affiche pour un capteur : une ligne par métrique. */
export interface Reading {
  source: string;
  sourceLabel: string;
  metric: string;
  metricLabel: string;
  value: number | null;
  unit: string | null;
  text: string;
}

export function statusLabel(status: string): string {
  switch (status) {
    case 'online':
      return 'En ligne';
    case 'offline':
      return 'Hors ligne';
    // Cycle de vie de l'appareil (ce que le serveur tient côté base).
    case 'pending':
    case 'provisioning':
      return 'En attente';
    case 'provisioned':
      return 'Appairé';
    case 'disabled':
      return 'Désactivé';
    default:
      return 'Inconnu';
  }
}

/**
 * Décalage entre l'horloge du serveur et celle du navigateur (serveur − navigateur).
 *
 * Le boîtier date ses mesures à l'heure du serveur ; le tableau de bord juge leur
 * fraîcheur. Comparer directement les deux montres fait afficher « Sans nouvelles »
 * alors que les mesures arrivent (VM en retard, machine qui sort de veille, fuseau
 * mal réglé). On mesure donc le décalage à chaque instantané et on le reporte.
 */
let clockSkewMs = 0;

/** Mémorise l'horloge annoncée par le serveur. Sans horloge, on revient à la nôtre. */
export function noteServerClock(
  serverNow: string | null | undefined,
  receivedAt = Date.now(),
): number {
  if (!serverNow) {
    clockSkewMs = 0;
    return 0;
  }
  const server = Date.parse(serverNow);
  clockSkewMs = Number.isNaN(server) ? 0 : server - receivedAt;
  return clockSkewMs;
}

/** Décalage courant, en millisecondes (utilisé par les tests et le diagnostic). */
export function serverClockSkew(): number {
  return clockSkewMs;
}

/**
 * A device is "fresh" when its last telemetry is recent enough to be trusted.
 *
 * `now` est l'heure du navigateur ; le décalage mesuré avec le serveur lui est
 * appliqué, pour comparer deux horloges comparables.
 */
export function isFresh(device: Pick<LiveDevice, 'last_seen'>, now = Date.now()): boolean {
  if (!device.last_seen) return false;
  const seen = Date.parse(device.last_seen);
  if (Number.isNaN(seen)) return false;
  // La télémétrie par défaut est à 30 s : trois intervalles avant de douter.
  return now + clockSkewMs - seen < 90_000;
}

export function formatMetric(metric: Metric | undefined): string {
  if (!metric || metric.value === null || metric.value === undefined) return '—';
  const unit = metric.unit ?? '';
  const value = Number.isInteger(metric.value)
    ? String(metric.value)
    : metric.value.toFixed(1);
  if (unit === 'celsius' || unit === '°C') return `${value} °C`;
  if (unit === 'percent' || unit === '%') return `${value} %`;
  return unit ? `${value} ${unit}` : value;
}

export function findDevice(
  devices: LiveDevice[],
  id: number,
): LiveDevice | undefined {
  return devices.find((device) => device.id === id);
}

/** Flattens a live device into one line per metric, ready to render. */
export function readings(device: LiveDevice | undefined): Reading[] {
  if (!device) return [];
  const out: Reading[] = [];
  for (const [source, metrics] of Object.entries(device.sensors)) {
    for (const [metric, value] of Object.entries(metrics)) {
      out.push({
        source,
        sourceLabel: humanize(source),
        metric,
        metricLabel: humanize(metric),
        value: value.value,
        unit: value.unit ?? null,
        text: formatMetric(value),
      });
    }
  }
  return out;
}

const LABELS: Record<string, string> = {
  ClimateSensor: 'Climat',
  SoilSensor: 'Sol',
  WaterPump: 'Pompe',
  GrowLamp: 'Lampe',
  temperature: 'Température',
  humidity: 'Humidité de l’air',
  moisture: 'Humidité du sol',
  telemetry_interval: 'Intervalle de télémétrie',
};

/** `WaterPump` -> `Pompe`, inconnu -> l'identifiant tel quel (jamais masqué). */
export function humanize(id: string): string {
  return LABELS[id] ?? id;
}

export function actuatorState(state: 'ON' | 'OFF' | undefined): string {
  if (state === 'ON') return 'Allumé';
  if (state === 'OFF') return 'Éteint';
  return 'Inconnu';
}

/** Commandes proposées pour un actionneur, dans l'ordre d'affichage. */
export function actuatorActions(): Array<'on' | 'off' | 'toggle'> {
  return ['on', 'off', 'toggle'];
}

export function actionLabel(action: string): string {
  switch (action) {
    case 'on':
      return 'Allumer';
    case 'off':
      return 'Éteindre';
    case 'toggle':
      return 'Basculer';
    case 'read':
      return 'Mesurer';
    case 'set':
      return 'Appliquer';
    default:
      return action;
  }
}
