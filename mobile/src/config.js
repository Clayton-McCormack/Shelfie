import Constants from 'expo-constants';

// Overrides auto-detection when set to an absolute base URL such as
// 'http://10.0.0.245:8000'. Needed only when the API runs on a different
// machine than the Metro bundler.
const MANUAL_API_BASE_URL = null;

const DJANGO_PORT = 8000;

/**
 * Derives the API base URL from the address Expo Go already used to fetch the
 * JS bundle.
 *
 * `hostUri` holds the Metro host, for example '10.0.0.245:8081'. The API runs
 * on that same machine, so reusing the host and substituting the Django port
 * yields a working base URL on any network without a source change.
 */
function inferApiBaseUrl() {
  const hostUri = Constants.expoConfig?.hostUri;
  if (!hostUri) return null;

  const host = hostUri.split(':')[0];
  if (!host) return null;

  return `http://${host}:${DJANGO_PORT}`;
}

export const API_BASE_URL = MANUAL_API_BASE_URL ?? inferApiBaseUrl();

// Spine detection followed by a hosted-model call can run for tens of seconds.
// Requests carry an explicit deadline so a stalled pipeline surfaces as an
// error rather than an unbounded wait.
export const REQUEST_TIMEOUT_MS = 60000;
