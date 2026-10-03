import { describe, expect, it } from 'vitest';

import {
  actuatorLabel,
  flattenReadings,
  formatValue,
  metricLabel,
  sensorLabel,
} from './format';
import type { Device } from './types';

describe('formatValue', () => {
  it('formats a celsius value', () => {
    expect(formatValue(18.34, 'celsius')).toBe('18.3 °C');
  });

  it('formats a percent value', () => {
    expect(formatValue(55, 'percent')).toBe('55 %');
  });

  it('formats an unknown unit', () => {
    expect(formatValue(2.5, 'lux')).toBe('2.5 lux');
  });
});

describe('labels', () => {
  it('maps known ids to French labels', () => {
    expect(sensorLabel('SoilSensor')).toBe('Sol (humidité)');
    expect(metricLabel('temperature')).toBe('Température');
    expect(actuatorLabel('WaterPump')).toBe('Pompe');
  });

  it('falls back to the raw id for unknown ids', () => {
    expect(sensorLabel('MysterySensor')).toBe('MysterySensor');
  });
});

describe('flattenReadings', () => {
  it('flattens nested sensor metrics into display rows', () => {
    const device: Device = {
      id: 'dev1',
      status: 'online',
      last_seen: null,
      sensors: {
        ClimateSensor: {
          temperature: { value: 18, unit: 'celsius' },
          humidity: { value: 55, unit: 'percent' },
        },
      },
      actuators: {},
    };

    const readings = flattenReadings(device);
    expect(readings).toHaveLength(2);
    expect(readings[0].metricLabel).toBe('Température');
    expect(readings[1].metricLabel).toBe('Humidité');
  });
});
