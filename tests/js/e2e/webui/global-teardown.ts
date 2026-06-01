/**
 * Global teardown to clean up resources after all tests.
 */

import * as fs from "fs";
import * as os from "os";

export default async function globalTeardown() {
  console.log("Global teardown: stopping all servers...");

  // Find all PID files
  const tmpdir = os.tmpdir();
  const pidFiles = fs.readdirSync(tmpdir)
    .filter(file => file.startsWith("vibe-e2e-server-") && file.endsWith(".pid"))
    .map(file => `${tmpdir}/${file}`);

  console.log(`Found ${pidFiles.length} server PID files`);

  const stopPromises = pidFiles.map(async (pidFile) => {
    try {
      const pid = parseInt(fs.readFileSync(pidFile, "utf-8").trim(), 10);
      const portMatch = pidFile.match(/vibe-e2e-server-(\d+)\.pid/);
      const port = portMatch ? portMatch[1] : "unknown";

      console.log(`Killing server on port ${port} with PID ${pid}...`);

      // Try graceful shutdown first
      try {
        process.kill(pid, "SIGTERM");
        // Wait for process to exit
        await new Promise<void>((resolve) => {
          const checkInterval = setInterval(() => {
            try {
              process.kill(pid, 0); // Check if process still exists
            } catch {
              clearInterval(checkInterval);
              resolve();
            }
          }, 100);
          setTimeout(() => {
            clearInterval(checkInterval);
            resolve();
          }, 2000);
        });
      } catch (err) {
        // Process might already be dead
        if ((err as NodeJS.ErrnoException).code !== "ESRCH") {
          console.warn(`Failed to send SIGTERM to PID ${pid}:`, err);
        }
      }

      // Force kill if still running
      try {
        process.kill(pid, 0); // Check if process still exists
        console.log(`Force killing server on port ${port} with PID ${pid}...`);
        process.kill(pid, "SIGKILL");
      } catch (err) {
        if ((err as NodeJS.ErrnoException).code !== "ESRCH") {
          console.warn(`Failed to send SIGKILL to PID ${pid}:`, err);
        }
      }

      // Clean up PID file
      fs.unlinkSync(pidFile);
      console.log(`Stopped server on port ${port}`);
    } catch (error) {
      console.warn(`Failed to stop server from PID file ${pidFile}:`, error);
    }
  });

  await Promise.all(stopPromises);
  console.log("Global teardown: all servers stopped");
}
