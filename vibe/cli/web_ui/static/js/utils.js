/**
 * Shared utility functions for the Web UI.
 */

/**
 * Get the base path for API and static asset URLs.
 * Falls back to '/' if not set by server template.
 * @returns {string} Base path (e.g., '/' or '/vibe/')
 */
export function getBasePath() {
    return globalThis.__VIBE_BASE_PATH__ || '/';
}

/**
 * Build a URL with the base path prefix.
 * @param {string} path - Relative path (e.g., 'api/status' or 'login')
 * @returns {string} Full URL (e.g., '/vibe/api/status')
 */
export function buildUrl(path) {
    return getBasePath() + path;
}
