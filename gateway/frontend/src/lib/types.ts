export interface Metric {
  value: number;
  unit: string | null;
}

export interface Device {
  id: string;
  status: 'online' | 'offline' | 'unknown';
  last_seen: number | null;
  sensors: Record<string, Record<string, Metric>>;
  actuators: Record<string, 'ON' | 'OFF'>;
}

export interface StatePayload {
  devices: Device[];
  count: number;
}
