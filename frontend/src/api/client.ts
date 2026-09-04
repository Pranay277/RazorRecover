/**
 * Thin fetch-based API transport for the RazorRecover backend.
 *
 * Kept separate from UI components and from endpoint definitions. Handles:
 * - network failures (backend unreachable) -> NetworkError
 * - non-2xx responses with a JSON body   -> ApiError (status + parsed body)
 * - invalid JSON payloads                -> JsonError
 */

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export class NetworkError extends Error {
  constructor(message?: string) {
    super(
      message ??
        'Unable to reach the RazorRecover backend. Check that the server is ' +
          'running and VITE_API_BASE_URL is correct.',
    );
    this.name = 'NetworkError';
  }
}

export class JsonError extends Error {
  constructor(message = 'The backend returned an invalid JSON response.') {
    super(message);
    this.name = 'JsonError';
  }
}

function extractMessage(status: number, body: unknown): string {
  if (body && typeof body === 'object') {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (Array.isArray(detail)) {
      const parts = detail.map((entry) => {
        if (entry && typeof entry === 'object' && 'msg' in entry) {
          return String((entry as { msg: unknown }).msg);
        }
        return String(entry);
      });
      if (parts.length > 0) {
        return parts.join('; ');
      }
    }
  }
  if (typeof body === 'string' && body.length > 0) {
    return body;
  }
  return `Request failed with status ${status}.`;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new NetworkError();
  }

  const text = await response.text();
  let body: unknown;
  if (text.length === 0) {
    body = undefined;
  } else {
    try {
      body = JSON.parse(text);
    } catch {
      throw new JsonError();
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, extractMessage(response.status, body), body);
  }
  return body as T;
}

export function toQueryString<T extends object>(params: T): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params) as [
    string,
    string | number | undefined | null,
  ][]) {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query.length > 0 ? `?${query}` : '';
}