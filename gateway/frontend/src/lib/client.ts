import { GrowHubClient } from '@growhub/client';

/**
 * One client for the whole app.
 *
 * `NEXT_PUBLIC_API_URL` is empty by default: calls go to the same origin and
 * Next proxies `/api/*` to the backend (see next.config.mjs), which is what
 * makes the session cookie a first-party cookie.
 */
let cached: GrowHubClient | null = null;

export function apiClient(): GrowHubClient {
  if (cached === null) {
    cached = new GrowHubClient({
      baseUrl: process.env.NEXT_PUBLIC_API_URL ?? '',
      credentials: 'include',
    });
  }
  return cached;
}
