import { afterEach, describe, expect, it, vi } from 'vitest';

import { GrowHubClient } from './client';
import { GrowHubError } from './errors';
import type { LiveSnapshot } from './types';

interface Call {
  url: string;
  init: RequestInit;
  body: unknown;
}

class Recorder {
  readonly calls: Call[] = [];

  constructor(
    private readonly handler: (
      url: string,
      init: RequestInit,
    ) => Response | Promise<Response> = () => jsonResponse(200, {}),
  ) {}

  fetch = async (url: string, init: RequestInit = {}): Promise<Response> => {
    const body = init.body ? JSON.parse(init.body as string) : undefined;
    this.calls.push({ url, init, body });
    return this.handler(url, init);
  };

  get last(): Call {
    return this.calls[this.calls.length - 1];
  }
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function clientWith(recorder: Recorder, csrf?: string): GrowHubClient {
  return new GrowHubClient({
    baseUrl: 'http://api.test',
    fetch: recorder.fetch,
    csrfToken: () => csrf ?? null,
  });
}

afterEach(() => {
  vi.useRealTimers();
});

// --- requests ---------------------------------------------------------------

describe('GrowHubClient requests', () => {
  it('posts the login payload and keeps the session cookie', async () => {
    const recorder = new Recorder(() =>
      jsonResponse(200, { id: 1, username: 'marius', email: 'm@test', is_staff: false }),
    );
    const user = await clientWith(recorder).login('marius', 'secret');

    expect(user.username).toBe('marius');
    expect(recorder.last.url).toBe('http://api.test/api/v1/auth/login');
    expect(recorder.last.init.method).toBe('POST');
    expect(recorder.last.body).toEqual({ username: 'marius', password: 'secret' });
    expect(recorder.last.init.credentials).toBe('include');
  });

  it('sends the CSRF token on unsafe methods but not on GET', async () => {
    const recorder = new Recorder(() => jsonResponse(200, {}));
    const client = clientWith(recorder, 'csrf-123');

    await client.me();
    await client.renameDevice(1, 'Serre');

    const headersOf = (call: Call) => call.init.headers as Record<string, string>;
    expect(headersOf(recorder.calls[0])['X-CSRFToken']).toBeUndefined();
    expect(headersOf(recorder.last)['X-CSRFToken']).toBe('csrf-123');
    expect(headersOf(recorder.last)['Content-Type']).toBe('application/json');
  });

  it('omits the CSRF header when no token is available', async () => {
    const recorder = new Recorder(() => jsonResponse(200, {}));
    await clientWith(recorder).renameDevice(1, 'Serre');
    expect((recorder.last.init.headers as Record<string, string>)['X-CSRFToken'])
      .toBeUndefined();
  });

  it('builds the telemetry query string and skips empty values', async () => {
    const recorder = new Recorder(() => jsonResponse(200, { points: [] }));
    await clientWith(recorder).telemetry(7, {
      metric: 'temperature',
      limit: 50,
      since: undefined,
      source: '',
    });
    expect(recorder.last.url).toBe(
      'http://api.test/api/v1/devices/7/telemetry?metric=temperature&limit=50',
    );
  });

  it('returns nothing for a 204', async () => {
    const recorder = new Recorder(() => new Response(null, { status: 204 }));
    await expect(clientWith(recorder).deleteDevice(3)).resolves.toBeUndefined();
  });

  it('posts a command with kind, action and args', async () => {
    const recorder = new Recorder(() => jsonResponse(201, { cmd_id: 'c1' }));
    await clientWith(recorder).sendCommand(2, 'actuators', 'on', { target: 'WaterPump' });

    expect(recorder.last.url).toBe('http://api.test/api/v1/devices/2/commands');
    expect(recorder.last.body).toEqual({
      kind: 'actuators',
      action: 'on',
      args: { target: 'WaterPump' },
    });
  });

  it('redeems a pairing code', async () => {
    const recorder = new Recorder(() => jsonResponse(201, { device: { id: 1 } }));
    await clientWith(recorder).redeemClaim('ABC234');
    expect(recorder.last.url).toBe('http://api.test/api/v1/devices/claims/redeem');
    expect(recorder.last.body).toEqual({ code: 'ABC234' });
  });

  it('cedes ownership with keep_access', async () => {
    const recorder = new Recorder(() => jsonResponse(200, {}));
    await clientWith(recorder).transfer(4, 'ami', false);
    expect(recorder.last.url).toBe('http://api.test/api/v1/devices/4/transfer');
    expect(recorder.last.body).toEqual({ username: 'ami', keep_access: false });
  });
});

// --- responses --------------------------------------------------------------

describe('GrowHubClient responses', () => {
  it('unwraps a paginated list', async () => {
    const recorder = new Recorder(() => jsonResponse(200, { count: 1, results: [{ id: 9 }] }));
    await expect(clientWith(recorder).listDevices()).resolves.toEqual([{ id: 9 }]);
  });

  it('accepts a bare array', async () => {
    const recorder = new Recorder(() => jsonResponse(200, [{ id: 9 }]));
    await expect(clientWith(recorder).listDevices()).resolves.toEqual([{ id: 9 }]);
  });

  it('surfaces the server message and flags an auth failure', async () => {
    const recorder = new Recorder(() =>
      jsonResponse(401, { detail: 'Identifiants invalides.' }),
    );
    const error = await clientWith(recorder)
      .login('marius', 'faux')
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(GrowHubError);
    expect((error as GrowHubError).message).toBe('Identifiants invalides.');
    expect((error as GrowHubError).isAuthError).toBe(true);
  });

  it('exposes field errors so a form can point at the right input', async () => {
    const recorder = new Recorder(() =>
      jsonResponse(400, { code: ['Ce champ est obligatoire.'] }),
    );
    const error = (await clientWith(recorder)
      .redeemClaim('')
      .catch((caught: unknown) => caught)) as GrowHubError;

    expect(error.status).toBe(400);
    expect(error.fields).toEqual({ code: ['Ce champ est obligatoire.'] });
    expect(error.message).toBe('Ce champ est obligatoire.');
  });

  it('keeps a non-JSON error body as the message', async () => {
    const recorder = new Recorder(() => new Response('Bad gateway', { status: 502 }));
    const error = (await clientWith(recorder)
      .live()
      .catch((caught: unknown) => caught)) as GrowHubError;
    expect(error.message).toBe('Bad gateway');
  });
});

// --- live -------------------------------------------------------------------

describe('GrowHubClient live', () => {
  it('polls when the runtime has no EventSource', async () => {
    vi.useFakeTimers();
    let snapshots = 0;
    const recorder = new Recorder(() =>
      jsonResponse(200, { devices: [], count: 0 } satisfies LiveSnapshot),
    );
    const stop = clientWith(recorder).subscribeLive(() => {
      snapshots += 1;
    }, undefined, { pollIntervalMs: 1000 });

    await vi.advanceTimersByTimeAsync(0);
    expect(snapshots).toBe(1);
    await vi.advanceTimersByTimeAsync(2500);
    expect(snapshots).toBe(3);
    stop();
    await vi.advanceTimersByTimeAsync(3000);
    expect(snapshots).toBe(3);
    expect(recorder.calls[0].url).toBe('http://api.test/api/v1/live');
  });

  it('reports polling errors without stopping', async () => {
    vi.useFakeTimers();
    const errors: unknown[] = [];
    let calls = 0;
    const recorder = new Recorder(() => {
      calls += 1;
      return jsonResponse(calls === 1 ? 500 : 200, { detail: 'panne' });
    });
    clientWith(recorder).subscribeLive(
      () => undefined,
      (error) => errors.push(error),
      { pollIntervalMs: 100 },
    );

    await vi.advanceTimersByTimeAsync(150);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toBeInstanceOf(GrowHubError);
  });

  it('reads an SSE stream fed in several chunks', async () => {
    const encoder = new TextEncoder();
    const frames = [
      'data: {"devices":[{"name":"Serre 1"}],"count":1}',
      '\n\ndata: {"devices":[{"name":"Serre 1"},{"name":"Serre 2"}],"count":2}\n\n',
    ];
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const frame of frames) controller.enqueue(encoder.encode(frame));
        controller.close();
      },
    });
    const recorder = new Recorder(() => new Response(body, { status: 200 }));

    const received: LiveSnapshot[] = [];
    await clientWith(recorder).readLiveStream((snapshot) => received.push(snapshot));

    expect(received).toHaveLength(2);
    expect(received[1].count).toBe(2);
    expect(received[1].devices[1].name).toBe('Serre 2');
  });

  it('refuses a stream that is not a stream', async () => {
    const recorder = new Recorder(() => jsonResponse(403, { detail: 'Refusé.' }));
    await expect(
      clientWith(recorder).readLiveStream(() => undefined),
    ).rejects.toBeInstanceOf(GrowHubError);
  });
});
