/**
 * API failure, with the server's own message.
 *
 * DRF answers either `{"detail": "…"}` or a field dictionary
 * (`{"code": ["Ce champ est obligatoire."]}`). Both are surfaced: a screen can
 * show `message`, and a form can attach `fields` to the offending inputs.
 */
export class GrowHubError extends Error {
  readonly status: number;
  readonly fields: Record<string, string[]>;

  constructor(
    message: string,
    status: number,
    fields: Record<string, string[]> = {},
  ) {
    super(message);
    this.name = 'GrowHubError';
    this.status = status;
    this.fields = fields;
  }

  /** 401/403: the caller must (re)authenticate or lacks the right. */
  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403;
  }

  static fromResponse(status: number, body: unknown): GrowHubError {
    const payload = (body ?? {}) as Record<string, unknown>;
    const detail = payload.detail;
    if (typeof detail === 'string' && detail.length > 0) {
      return new GrowHubError(detail, status);
    }

    const fields: Record<string, string[]> = {};
    for (const [key, value] of Object.entries(payload)) {
      if (Array.isArray(value)) fields[key] = value.map(String);
      else if (typeof value === 'string') fields[key] = [value];
    }

    const first = Object.values(fields)[0]?.[0];
    const message =
      first ?? `Erreur ${status}${Object.keys(fields).length ? '' : ' : réponse inattendue'}`;
    return new GrowHubError(message, status, fields);
  }
}
