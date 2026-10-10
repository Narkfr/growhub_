import { describe, expect, it } from 'vitest';

import type { LiveDevice } from '@growhub/client';

import {
  actionLabel,
  actuatorActions,
  actuatorState,
  formatMetric,
  humanize,
  isFresh,
  readings,
  statusLabel,
} from './display';

function liveDevice(overrides: Partial<LiveDevice> = {}): LiveDevice {
  return {
    id: 1,
    device_id: 'ghb-3f2a91',
    name: 'Serre tomates',
    slug: 'ghb-3f2a91',
    status: 'online',
    is_online: true,
    last_seen: new Date().toISOString(),
    site: null,
    sensors: {},
    actuators: {},
    ts: null,
    ...overrides,
  };
}

describe('statusLabel', () => {
  it('translates the device statuses', () => {
    expect(statusLabel('online')).toBe('En ligne');
    expect(statusLabel('offline')).toBe('Hors ligne');
    expect(statusLabel('provisioning')).toBe('En attente');
    // Cycle de vie : ce que le serveur renvoie pour l'appareil lui-même.
    expect(statusLabel('pending')).toBe('En attente');
    expect(statusLabel('provisioned')).toBe('Appairé');
    expect(statusLabel('disabled')).toBe('Désactivé');
    expect(statusLabel('autre')).toBe('Inconnu');
  });
});

describe('isFresh', () => {
  const now = Date.parse('2026-10-09T12:00:00Z');

  it('accepts a recent reading', () => {
    expect(isFresh({ last_seen: '2026-10-09T11:59:30Z' }, now)).toBe(true);
  });

  it('rejects a stale reading', () => {
    expect(isFresh({ last_seen: '2026-10-09T11:50:00Z' }, now)).toBe(false);
  });

  it('rejects a missing or unparsable date', () => {
    expect(isFresh({ last_seen: null }, now)).toBe(false);
    expect(isFresh({ last_seen: 'pas une date' }, now)).toBe(false);
  });
});

describe('formatMetric', () => {
  it('renders a celsius value with its unit', () => {
    expect(formatMetric({ value: 18.34, unit: 'celsius' })).toBe('18.3 °C');
  });

  it('renders integers without a decimal part', () => {
    expect(formatMetric({ value: 55, unit: 'percent' })).toBe('55 %');
  });

  it('keeps an unknown unit visible', () => {
    expect(formatMetric({ value: 2.5, unit: 'lux' })).toBe('2.5 lux');
  });

  it('shows a dash instead of inventing a value', () => {
    expect(formatMetric(undefined)).toBe('—');
    expect(formatMetric({ value: null, unit: 'celsius' })).toBe('—');
  });
});

describe('readings', () => {
  it('flattens a device into one line per metric, with labels', () => {
    const device = liveDevice({
      sensors: {
        ClimateSensor: {
          temperature: { value: 18, unit: 'celsius' },
          humidity: { value: 55, unit: 'percent' },
        },
      },
    });

    const lines = readings(device);
    expect(lines).toHaveLength(2);
    expect(lines[0].sourceLabel).toBe('Climat');
    expect(lines[0].metricLabel).toBe('Température');
    expect(lines[0].text).toBe('18 °C');
    expect(lines[1].text).toBe('55 %');
  });

  it('returns nothing for a missing device', () => {
    expect(readings(undefined)).toEqual([]);
  });
});

describe('labels', () => {
  it('translates known identifiers', () => {
    expect(humanize('WaterPump')).toBe('Pompe');
    expect(humanize('moisture')).toBe('Humidité du sol');
  });

  it('never hides an unknown identifier behind a generic label', () => {
    expect(humanize('MysterySensor')).toBe('MysterySensor');
  });

  it('translates actuator states and actions', () => {
    expect(actuatorState('ON')).toBe('Allumé');
    expect(actuatorState('OFF')).toBe('Éteint');
    expect(actuatorState(undefined)).toBe('Inconnu');
    expect(actuatorActions()).toEqual(['on', 'off', 'toggle']);
    expect(actionLabel('toggle')).toBe('Basculer');
    expect(actionLabel('mesure')).toBe('mesure');
  });
});
