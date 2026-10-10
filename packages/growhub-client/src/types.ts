/**
 * Types of the GrowHub API (v1), shared by the dashboard and the mobile app.
 *
 * They mirror the DRF serializers field for field: when a serializer changes,
 * this file changes, and TypeScript points at every call site that must adapt.
 */

export type Role = 'owner' | 'member' | 'viewer';

/** Statut d'exécution, publié par le boîtier lui-même (`online` / `offline`). */
export type RuntimeStatus = 'online' | 'offline';

/** Statut de cycle de vie de l'appareil, tenu par le serveur. */
export type DeviceStatus = 'pending' | 'provisioned' | 'disabled';

export type CommandKind = 'actuators' | 'sensors' | 'config';

export type CommandStatus = 'pending' | 'sent' | 'acked' | 'failed' | 'expired';

export interface User {
  id: number;
  username: string;
  email: string;
  display_name?: string;
  label?: string;
  is_staff: boolean;
}

export interface Membership {
  id: number;
  user: number;
  username: string;
  user_label: string;
  role: Role;
  created_at: string;
}

export interface Capability {
  id: number;
  kind: 'sensor' | 'actuator' | 'config';
  name: string;
  metrics: string[];
  unit: string | null;
  active: boolean;
}

export interface Device {
  id: number;
  device_id: string;
  slug: string;
  name: string;
  model: string;
  fw_version: string;
  status: DeviceStatus;
  site: number | null;
  site_name: string | null;
  last_seen: string | null;
  provisioned_at: string | null;
  is_online: boolean;
  role: Role | null;
  capabilities: Capability[];
  memberships: Membership[];
  created_at: string;
}

/** One device as it appears in `/live` and in the SSE stream. */
export interface LiveDevice {
  id: number;
  device_id: string;
  name: string;
  slug: string;
  status: RuntimeStatus;
  is_online: boolean;
  last_seen: string | null;
  site: string | null;
  sensors: Record<string, Record<string, Metric>>;
  actuators: Record<string, 'ON' | 'OFF'>;
  ts: string | null;
}

export interface Metric {
  value: number | null;
  unit?: string | null;
}

export interface LiveSnapshot {
  devices: LiveDevice[];
  count: number;
}

export interface TelemetryPoint {
  id: number;
  device: number;
  ts: string;
  source: string;
  metric: string;
  value: number | null;
  unit: string | null;
}

export interface TelemetryHistory {
  device_id: string;
  metric: string | null;
  count: number;
  points: TelemetryPoint[];
}

export interface CommandAudit {
  id: number;
  cmd_id: string;
  device_id: string;
  device: number;
  user: number;
  user_label: string | null;
  kind: CommandKind;
  action: string;
  args: Record<string, unknown>;
  status: CommandStatus;
  error: string;
  created_at: string;
  acked_at: string | null;
}

export interface Site {
  id: number;
  name: string;
  description: string;
  created_at: string;
}

export interface PairingResult {
  device: Device;
  claim: unknown;
}

/** Credentials handed to a freshly flashed device (staff only, shown once). */
export interface ProvisionResult {
  device_id: string;
  username: string;
  password: string;
  broker: string;
  port: number;
  pairing_code: string;
}
