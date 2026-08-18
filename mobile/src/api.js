import { API_BASE_URL, REQUEST_TIMEOUT_MS } from './config';

/**
 * Single error type for every client-side failure, carrying a message fit for
 * display.
 *
 * Screens render `message` without distinguishing a timeout from a 500 from
 * unparseable JSON. Error handling therefore stays in this module, and no code
 * path can terminate on a blank screen.
 */
export class ApiError extends Error {
  constructor(message, { cause } = {}) {
    super(message);
    this.name = 'ApiError';
    this.cause = cause;
  }
}

/**
 * Performs a request with a deadline, uniform error messages, and no silent
 * JSON failures.
 */
export async function request(path, { method = 'GET', body, timeoutMs = REQUEST_TIMEOUT_MS } = {}) {
  if (!API_BASE_URL) {
    throw new ApiError(
      'Could not work out the server address. Set MANUAL_API_BASE_URL in src/config.js.',
    );
  }

  // fetch has no native timeout. Without an explicit abort, an unreachable
  // server leaves the interface spinning indefinitely.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      body,
      signal: controller.signal,
      headers: body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    });
  } catch (err) {
    // Aborts and unreachable hosts both surface here but call for different
    // remedies, so they are reported as distinct messages.
    if (err.name === 'AbortError') {
      throw new ApiError(`The server took longer than ${Math.round(timeoutMs / 1000)}s to reply.`, {
        cause: err,
      });
    }
    throw new ApiError(`Could not reach the server at ${API_BASE_URL}.`, { cause: err });
  } finally {
    clearTimeout(timer);
  }

  const text = await response.text();

  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (err) {
      // Django debug tracebacks, proxies, and captive portals all return HTML
      // where JSON is expected. Such a response is a failure, never an empty
      // result.
      throw new ApiError('The server sent back something that was not JSON.', { cause: err });
    }
  }

  if (!response.ok) {
    throw new ApiError(data?.detail ?? `Server returned ${response.status}.`);
  }

  return data;
}
