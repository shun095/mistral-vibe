/**
 * Server manager for starting/stopping the Vibe CLI with web UI during E2E tests.
 */

import * as child_process from "child_process";
import * as http from "http";
import * as net from "net";
import * as os from "os";
import * as path from "path";
import * as fs from "fs";

export interface ServerConfig {
  port: number;
  token: string;
}

export class ServerManager {
  private process: child_process.ChildProcess | null = null;
  private config: ServerConfig;
  private started: boolean = false;
  private actualPort: number | null = null;
  private e2eTestDir: string | null = null;
  private serverPidFile: string | null = null;

  constructor(config: ServerConfig) {
    this.config = config;
  }

  /**
   * Check if a port is available.
   */
  private isPortAvailable(port: number): Promise<boolean> {
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
   * Find an available port starting from the given port.
   */
  private async findAvailablePort(startPort: number): Promise<number> {
    for (let port = startPort; port < startPort + 100; port++) {
      if (await this.isPortAvailable(port)) {
        return port;
      }
    }
    throw new Error(`Could not find an available port starting from ${startPort}`);
  }

  /**
   * Kill any existing process on the given port.
   */
  private async killProcessOnPort(port: number): Promise<void> {
    try {
      const { execSync } = require("child_process");
      const output = execSync(
        `lsof -ti :${port} 2>/dev/null || true`,
        { encoding: "utf-8" }
      );
      const pids = output.trim().split("\n").filter((pid: string) => pid.length > 0);
      for (const pid of pids) {
        try {
          process.kill(parseInt(pid, 10), "SIGKILL");
        } catch {
          // Ignore errors
        }
      }
      // Wait a moment for the port to be released
      await new Promise((resolve) => setTimeout(resolve, 500));
    } catch {
      // Ignore errors
    }
  }

  async start(): Promise<void> {
    if (this.started) {
      return;
    }

    // Use the specified port directly (pre-allocated by global setup)
    // Only find available port if the specified port is in use
    let port = this.config.port;
    if (!(await this.isPortAvailable(port))) {
      console.log(`Port ${port} is in use, finding available port...`);
      port = await this.findAvailablePort(port);
    }
    this.actualPort = port;

    // Kill any existing process on the port
    await this.killProcessOnPort(port);

    // Set up E2E test directory with mock data
    this.e2eTestDir = this.setupE2eTestDir();

    const env = {
      ...process.env,
      VIBE_WEB_TOKEN: this.config.token,
      VIBE_ALLOW_URL_TOKEN: "true", // Enable URL token auth for E2E tests
      VIBE_E2E_TEST: "true",
      VIBE_E2E_TEST_DIR: this.e2eTestDir,
      PYTHONUNBUFFERED: "1",
    };

    console.log(`Starting Vibe CLI with WebUI on port ${port}...`);
    console.log(`Using E2E test directory: ${this.e2eTestDir}`);

    return new Promise((resolve, reject) => {
      // Start uv run vibe --web
      this.process = child_process.spawn("uv", [
        "run",
        "vibe",
        "--web",
        "--web-port",
        String(this.actualPort),
      ], {
        env,
        stdio: ["ignore", "pipe", "pipe"],
      });

      // Save server PID to file for global teardown
      if (this.process.pid) {
        this.serverPidFile = `/tmp/vibe-e2e-server-${this.actualPort}.pid`;
        fs.writeFileSync(this.serverPidFile, String(this.process.pid), "utf-8");
        console.log(`Server PID ${this.process.pid} saved to ${this.serverPidFile}`);
      }

      // Capture stdout/stderr for debugging
      let stdout = "";
      let stderr = "";
      this.process.stdout?.on("data", (data: Buffer) => {
        stdout += data.toString();
      });
      this.process.stderr?.on("data", (data: Buffer) => {
        stderr += data.toString();
      });

      // Wait for server to be ready
      this.waitForServer().then(() => {
        this.started = true;
        console.log(`Vibe CLI with WebUI started successfully on port ${this.actualPort}`);
        resolve();
      }).catch((error) => {
        if (this.process) {
          this.process.kill();
        }
        console.error("Server stdout:", stdout);
        console.error("Server stderr:", stderr);
        reject(error);
      });
    });
  }

  async stop(): Promise<void> {
    if (!this.started || !this.process) {
      return;
    }

    console.log("Stopping Vibe CLI...");

    return new Promise((resolve) => {
      this.process?.kill("SIGTERM");

      // Force kill after timeout
      setTimeout(() => {
        this.process?.kill("SIGKILL");
        resolve();
      }, 2000);

      this.process?.on("exit", () => {
        this.started = false;
        this.process = null;
        console.log("Vibe CLI stopped");
        this.cleanupE2eTestDir();
      });
    });
  }

  private waitForServer(): Promise<void> {
    const maxAttempts = 120; // Increased from 60 to 120 (120 seconds total)
    const interval = 1000;

    console.log(
      `Waiting for server on port ${this.actualPort} (max ${maxAttempts}s)...`
    );

    return new Promise((resolve, reject) => {
      let attempts = 0;

      const check = () => {
        attempts++;
        const req = http.get(
          `http://127.0.0.1:${this.actualPort}/health`,
          (res) => {
            if (res.statusCode === 200) {
              console.log(`Server ready after ${attempts} attempts`);
              resolve();
            } else {
              if (attempts >= maxAttempts) {
                reject(new Error(`Server returned status ${res.statusCode}`));
              } else {
                if (attempts % 10 === 0) {
                  console.log(
                    `Health check attempt ${attempts}/${maxAttempts}...`
                  );
                }
                setTimeout(check, interval);
              }
            }
          }
        );

        req.on("error", (err) => {
          if (attempts >= maxAttempts) {
            console.error(
              `Server failed to start after ${maxAttempts * interval}ms`
            );
            reject(
              new Error(
                `Server failed to start after ${maxAttempts * interval}ms: ${err.message}`
              )
            );
          } else {
            if (attempts % 10 === 0) {
              console.log(
                `Health check attempt ${attempts}/${maxAttempts} (connection refused)...`
              );
            }
            setTimeout(check, interval);
          }
        });

        req.setTimeout(5000, () => {
          req.destroy();
          if (attempts >= maxAttempts) {
            reject(new Error("Server health check timeout"));
          } else {
            setTimeout(check, interval);
          }
        });
      };

      check();
    });
  }

  getUrl(): string {
    return `http://127.0.0.1:${this.actualPort}`;
  }

  getToken(): string {
    return this.config.token;
  }

  getPort(): number {
    return this.actualPort || this.config.port;
  }

  /**
   * Set up E2E test directory with mock data.
   */
  private setupE2eTestDir(): string {
    const testDir = path.join(os.tmpdir(), `vibe-e2e-test-${process.pid}-${Date.now()}`);

    // Clean up any existing test directory
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }

    // Create directory structure
    fs.mkdirSync(testDir, { recursive: true });
    fs.mkdirSync(path.join(testDir, "logs", "session"), { recursive: true });

    // Create mock history file with sample prompts
    const historyFile = path.join(testDir, "vibehistory");
    const samplePrompts = [
      "What is the capital of France?",
      "How do I install Python packages?",
      "Explain the concept of recursion in programming",
      "Write a Python function to reverse a string",
      "What is the difference between list and tuple in Python?",
    ];

    fs.writeFileSync(historyFile, samplePrompts.join("\n"), "utf-8");

    console.log(`Created E2E test directory: ${testDir}`);
    return testDir;
  }

  /**
   * Clean up E2E test directory.
   */
  private cleanupE2eTestDir(): void {
    if (this.e2eTestDir && fs.existsSync(this.e2eTestDir)) {
      try {
        fs.rmSync(this.e2eTestDir, { recursive: true, force: true });
        console.log(`Cleaned up E2E test directory: ${this.e2eTestDir}`);
      } catch (err) {
        console.warn(`Failed to clean up E2E test directory: ${err}`);
      }
    }

    // Clean up PID file
    if (this.serverPidFile && fs.existsSync(this.serverPidFile)) {
      try {
        fs.unlinkSync(this.serverPidFile);
        console.log(`Cleaned up PID file: ${this.serverPidFile}`);
      } catch (err) {
        console.warn(`Failed to clean up PID file: ${err}`);
      }
    }
  }
}
