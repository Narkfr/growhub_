import type { Device } from './types';

const SENSOR_LABELS: Record<string, string> = {
  ClimateSensor: 'Climat (DHT11)',
  SoilSensor: 'Sol (humidité)',
};

const METRIC_LABELS: Record<string, string> = {
  temperature: 'Température',
  humidity: 'Humidité',
  moisture: 'Humidité',
};

const ACTUATOR_LABELS: Record<string, string> = {
  WaterPump: 'Pompe',
  GrowLamp: 'Lampe',
};

export interface FlatReading {
  sensorId: string;
  sensorLabel: string;
  metric: string;
  metricLabel: string;
  value: number;
  unit: string | null;
}

export function sensorLabel(id: string): string {
  return SENSOR_LABELS[id] ?? id;
}

export function metricLabel(id: string): string {
  return METRIC_LABELS[id] ?? id;
}

export function actuatorLabel(id: string): string {
  return ACTUATOR_LABELS[id] ?? id;
}

export function formatValue(
  value: number,
  unit: string | null,
  decimals = 1,
): string {
  const n = Number(value.toFixed(decimals));
  if (unit === 'celsius') return `${n} °C`;
  if (unit === 'percent') return `${n} %`;
  return unit ? `${n} ${unit}` : String(n);
}

export function flattenReadings(device: Device): FlatReading[] {
  const out: FlatReading[] = [];
  for (const [sensorId, metrics] of Object.entries(device.sensors)) {
    for (const [metric, m] of Object.entries(metrics)) {
      out.push({
        sensorId,
        sensorLabel: sensorLabel(sensorId),
        metric,
        metricLabel: metricLabel(metric),
        value: m.value,
        unit: m.unit,
      });
    }
  }
  return out;
}
