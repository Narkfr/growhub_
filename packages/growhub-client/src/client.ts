/**
 * GrowHub API client — framework free, shared by the dashboard and, later, the
 * mobile app.
 *
 * Nothing here touches `window` or a specific runtime: `fetch` is injected (and
 * defaulted), the CSRF token is read from a cookie only when a document exists,
 * and the live stream falls back to polling when `EventSource` is unavailable
 * (React Native has none). That is what makes one client serve both apps.
 */

import { GrowHubError } from './errors';
import { parseSseChunk, parseSseJson, type SseEvent } from './sse';
import type {
  CommandAudit,
  CommandKind,
  Device,
  LiveSnapshot,
  Membership,
  PairingResult,
  ProvisionResult,
  Role,
  Site,
  TelemetryHistory,
  User,
} from './types';

export type FetchLike = (
  input: string,
  init?: RequestInit,
) => Promise<Response>;

export interface ClientOptions {
  /** API root, e.g. `http://127.0.0.1:8000` or `''` behind a same-origin proxy. */
  baseUrl?: string;
  /** Injected for tests and non-browser runtimes (React Native). */
  fetch?: FetchLike;
  /** `include` in a browser (session cookie), `omit` for token-less clients. */
  credentials?: RequestCredentials;
  /** CSRF token for unsafe methods; defaults to the `csrftoken` cookie. */
  csrfToken?: () => string | null;
}

export interface LiveSubscriptionOptions {
  /** Pause between two snapshot polls when SSE is not used. */
  pollIntervalMs?: number;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | undefined | null>;
}

function hasDocument(): boolean {
  return typeof document !== 'undefined';
}

export function readCsrfCookie(name = 'csrftoken'): string | null {
  if (!hasDocument()) return null;
  const match = document.cookie.match(new RegExp(`(^|;\\s*)${name}=([^;]*)`));
  return match ? decodeURIComponent(match[2]) : null;
}

/** DRF paginates list endpoints; accept both shapes. */
function unwrap<T>(payload: T | { results: T }): T {
  if (payload && typeof payload === 'object' && 'results' in payload) {
    return (payload as { results: T }).results;
  }
  return payload as T;
}

export class GrowHubClient {
  readonly baseUrl: string;
  private readonly fetchImpl: FetchLike;
  private readonly credentials: RequestCredentials;
  private readonly csrfToken: () => string | null;

  constructor(options: ClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? '').replace(/\/$/, '');
    const globalFetch = (globalThis as { fetch?: FetchLike }).fetch;
    if (!options.fetch && !globalFetch) {
      throw new Error('Aucune implémentation de fetch : en passer une dans les options.');
    }
    // Le `fetch` du navigateur est une fonction native de `window` : appelé comme
    // méthode de cet objet-ci, il lève « Illegal invocation » *avant* toute
    // requête — sans rien envoyer et sans laisser de trace réseau. On l'appelle
    // donc par une fonction fléchée, qui ne lui impose aucun récepteur.
    this.fetchImpl =
      options.fetch ??
      ((input, init) => (globalFetch as FetchLike)(input, init));
    this.credentials = options.credentials ?? 'include';
    this.csrfToken = options.csrfToken ?? (() => readCsrfCookie());
  }

  private url(path: string, query?: RequestOptions['query']): string {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(query ?? {})) {
      if (value !== undefined && value !== null && value !== '') {
        search.append(key, String(value));
      }
    }
    const suffix = search.toString();
    return `${this.baseUrl}${path}${suffix ? `?${suffix}` : ''}`;
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const method = options.method ?? 'GET';
    const headers: Record<string, string> = { Accept: 'application/json' };
    const init: RequestInit = { method, credentials: this.credentials, headers };

    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      const token = this.csrfToken();
      if (token) headers['X-CSRFToken'] = token;
    }

    const response = await this.fetchImpl(this.url(path, options.query), init);
    if (response.status === 204) return undefined as T;

    const text = await response.text();
    const payload: unknown = text ? safeJson(text) : null;
    if (!response.ok) {
      throw GrowHubError.fromResponse(response.status, payload);
    }
    return payload as T;
  }

  // --- authentication ------------------------------------------------------

  async login(username: string, password: string): Promise<User> {
    return this.request<User>('/api/v1/auth/login', {
      method: 'POST',
      body: { username, password },
    });
  }

  async logout(): Promise<void> {
    await this.request<void>('/api/v1/auth/logout', { method: 'POST' });
  }

  /** Current profile, and the request that also seeds the CSRF cookie. */
  async me(): Promise<User> {
    return this.request<User>('/api/v1/auth/me');
  }

  // --- devices -------------------------------------------------------------

  async listDevices(): Promise<Device[]> {
    return unwrap(await this.request<Device[] | { results: Device[] }>('/api/v1/devices'));
  }

  async getDevice(id: number | string): Promise<Device> {
    return this.request<Device>(`/api/v1/devices/${id}`);
  }

  async renameDevice(id: number | string, name: string): Promise<Device> {
    return this.request<Device>(`/api/v1/devices/${id}`, {
      method: 'PATCH',
      body: { name },
    });
  }

  async deleteDevice(id: number | string): Promise<void> {
    await this.request<void>(`/api/v1/devices/${id}`, { method: 'DELETE' });
  }

  // --- membership and ownership -------------------------------------------

  async listMembers(id: number | string): Promise<Membership[]> {
    return unwrap(
      await this.request<Membership[] | { results: Membership[] }>(
        `/api/v1/devices/${id}/members`,
      ),
    );
  }

  async addMember(
    id: number | string,
    username: string,
    role: Role = 'member',
  ): Promise<Membership> {
    return this.request<Membership>(`/api/v1/devices/${id}/members`, {
      method: 'POST',
      body: { username, role },
    });
  }

  async removeMember(id: number | string, userId: number): Promise<void> {
    await this.request<void>(`/api/v1/devices/${id}/members/${userId}`, {
      method: 'DELETE',
    });
  }

  async transfer(
    id: number | string,
    username: string,
    keepAccess = true,
  ): Promise<Device> {
    return this.request<Device>(`/api/v1/devices/${id}/transfer`, {
      method: 'POST',
      body: { username, keep_access: keepAccess },
    });
  }

  // --- pairing and provisioning -------------------------------------------

  /** Redeems the code shown on the device's screen. */
  async redeemClaim(code: string): Promise<PairingResult> {
    return this.request<PairingResult>('/api/v1/devices/claims/redeem', {
      method: 'POST',
      body: { code },
    });
  }

  /** Staff only: registers a flashed device and returns its pairing code. */
  async createClaim(params: {
    deviceId: string;
    code?: string;
    name?: string;
    model?: string;
    ttlHours?: number;
  }): Promise<{ device: Device; code: string }> {
    return this.request<{ device: Device; code: string }>('/api/v1/devices/claims', {
      method: 'POST',
      body: {
        device_id: params.deviceId,
        code: params.code,
        name: params.name,
        model: params.model,
        ttl_hours: params.ttlHours,
      },
    });
  }

  /** Staff only: generates MQTT credentials and pushes them to the device. */
  async provisionDevice(
    id: number | string,
    secretsPath?: string,
  ): Promise<ProvisionResult> {
    return this.request<ProvisionResult>(`/api/v1/devices/${id}/provision`, {
      method: 'POST',
      body: secretsPath ? { secrets_path: secretsPath } : {},
    });
  }

  async revokeProvisioning(id: number | string): Promise<void> {
    await this.request<void>(`/api/v1/devices/${id}/provision/revoke`, {
      method: 'POST',
    });
  }

  // --- telemetry, commands, live ------------------------------------------

  async telemetry(
    id: number | string,
    params: { metric?: string; source?: string; since?: string; limit?: number } = {},
  ): Promise<TelemetryHistory> {
    return this.request<TelemetryHistory>(`/api/v1/devices/${id}/telemetry`, {
      query: params,
    });
  }

  async listCommands(id: number | string): Promise<CommandAudit[]> {
    return unwrap(
      await this.request<CommandAudit[] | { results: CommandAudit[] }>(
        `/api/v1/devices/${id}/commands`,
      ),
    );
  }

  async sendCommand(
    id: number | string,
    kind: CommandKind,
    action: string,
    args: Record<string, unknown> = {},
  ): Promise<CommandAudit> {
    return this.request<CommandAudit>(`/api/v1/devices/${id}/commands`, {
      method: 'POST',
      body: { kind, action, args },
    });
  }

  async live(): Promise<LiveSnapshot> {
    return this.request<LiveSnapshot>('/api/v1/live');
  }

  async listSites(): Promise<Site[]> {
    return unwrap(await this.request<Site[] | { results: Site[] }>('/api/v1/sites'));
  }

  /**
   * Live state of every device the user can see.
   *
   * SSE when the runtime has it (2 s server-side), polling otherwise; both paths
   * deliver the same snapshot shape, so a screen does not know which is used.
   * Returns the function that stops the subscription.
   */
  subscribeLive(
    onSnapshot: (snapshot: LiveSnapshot) => void,
    onError?: (error: unknown) => void,
    options: LiveSubscriptionOptions = {},
  ): () => void {
    const EventSourceImpl = (globalThis as { EventSource?: typeof EventSource })
      .EventSource;
    const streamUrl = this.url('/api/v1/live/stream');

    if (EventSourceImpl) {
      const source = new EventSourceImpl(streamUrl, {
        withCredentials: this.credentials === 'include',
      });
      source.onmessage = (message: MessageEvent<string>) => {
        const parsed = parseSseJson<LiveSnapshot>({
          event: 'message',
          data: message.data,
        });
        if (parsed) onSnapshot(parsed);
      };
      if (onError) source.onerror = (event: Event) => onError(event);
      return () => source.close();
    }

    let stopped = false;
    const interval = options.pollIntervalMs ?? 2000;
    const tick = async () => {
      if (stopped) return;
      try {
        onSnapshot(await this.live());
      } catch (error) {
        if (onError) onError(error);
      }
    };
    void tick();
    const handle = setInterval(() => void tick(), interval);
    return () => {
      stopped = true;
      clearInterval(handle);
    };
  }

  /**
   * Reads an SSE stream from an injected fetch (used by tests and by runtimes
   * without `EventSource` but with streaming responses).
   */
  async readLiveStream(
    onSnapshot: (snapshot: LiveSnapshot) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const response = await this.fetchImpl(this.url('/api/v1/live/stream'), {
      method: 'GET',
      credentials: this.credentials,
      headers: { Accept: 'text/event-stream' },
      signal,
    });
    if (!response.ok || !response.body) {
      throw GrowHubError.fromResponse(response.status, null);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { events, rest } = parseSseChunk(buffer);
      buffer = rest;
      for (const event of events) {
        const snapshot = parseSseJson<LiveSnapshot>(event as SseEvent);
        if (snapshot) onSnapshot(snapshot);
      }
    }
  }
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}
