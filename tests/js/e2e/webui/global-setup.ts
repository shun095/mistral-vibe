/**
 * Global setup to pre-allocate ports for all workers.
 * This prevents port collision between parallel workers.
 */

import { FullConfig } from "@playwright/test";
import * as net from "net";
import * as fs from "fs";
import * as os from "os";

/**
 * Check if a port is available.
 */
function isPortAvailable(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => {
      resolve(false);
    });
    server.once("listening", () => {
      server.close();
      resolve(true);
    });
    server.listen(port, "127.0.0.1");
  });
}

/**
 * Find N available ports starting from startPort.
 */
async function findAvailablePorts(startPort: number, count: number): Promise<number[]> {
  const availablePorts: number[] = [];
  let port = startPort;
  const maxPort = startPort + 1000; // Safety limit

  while (availablePorts.length < count && port < maxPort) {
    if (await isPortAvailable(port)) {
      availablePorts.push(port);
    }
    port++;
  }

  if (availablePorts.length < count) {
    throw new Error(
      `Could not find ${count} available ports starting from ${startPort}. Found ${availablePorts.length}.`
    );
  }

  return availablePorts;
}

/**
 * Global setup runs once before all tests.
 * Pre-allocates ports for all workers and saves to a file.
 */
export default async function globalSetup(config: FullConfig) {
  // Determine the number of workers needed
  // Each browser project gets its own set of workers
  const workersPerProject = typeof config.workers === "number" ? config.workers : 4;
  const numProjects = config.projects.length;

  // Total ports needed = workers per project (each project runs separately)
  // We'll allocate ports per worker index, so we need max workers per project
  const totalPortsNeeded = workersPerProject;

  console.log(`Global setup: allocating ${totalPortsNeeded} ports for workers...`);

  // Find available ports
  const ports = await findAvailablePorts(9100, totalPortsNeeded);

  console.log(`Global setup: allocated ports: ${ports.join(", ")}`);

  // Save ports to a file that workers can read
  const portsFile = os.tmpdir() + "/vibe-e2e-ports.json";
  fs.writeFileSync(portsFile, JSON.stringify(ports), "utf-8");

  console.log(`Global setup: ports saved to ${portsFile}`);

  // Return cleanup function
  return () => {
    try {
      fs.unlinkSync(portsFile);
      console.log(`Global setup: cleaned up ports file ${portsFile}`);
    } catch {
      // Ignore errors
    }
  };
}
