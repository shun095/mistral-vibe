/**
 * Format elapsed time in seconds to a human-readable string.
 *
 * @param {number} seconds - Elapsed time in seconds.
 * @returns {string} Formatted string: "0.5s", "2.3s", "1m 0.0s", "1m 23.4s".
 */
function formatDuration(seconds) {
    if (seconds < 60) {
        return `${seconds.toFixed(1)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remaining = seconds % 60;
    return `${minutes}m ${remaining.toFixed(1)}s`;
}

export { formatDuration };
