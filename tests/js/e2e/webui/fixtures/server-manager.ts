/**
 * Server manager for starting/stopping the Vibe CLI with web UI during E2E tests.
 */

import * as child_process from "child_process";
import * as http from "http";
import * as net from "net";
import * as os from "os";
import * as path from "path";
import * as fs from "fs";

// E2E test configuration constants
const PROJECT_ROOT = path.resolve(__dirname, "../../../../..");

// Minimal config.toml for E2E tests - matches actual defaults from vibe/core/config/_settings.py
// Intentionally omits save_dir to allow VIBE_HOME env var to control session log location
// Includes a dummy MCP server for MCP modal E2E tests (no tools, toggle-able)
// Uses /bin/true which exits immediately — server shows with 0 tools, no blocking
const E2E_CONFIG_TOML = `enable_update_checks = false
enable_auto_update = false

[session_logging]
enabled = true
session_prefix = "session"

[tools.read_file]
max_read_bytes = 64000

[tools.write_file]
max_write_bytes = 64000

[[mcp_servers]]
name = "e2e_test_server"
transport = "stdio"
command = "/bin/true"
args = []
`;

// Config with code-server enabled — used by visual integration tests
// Port is substituted dynamically via placeholder
const E2E_CONFIG_WITH_CODE_SERVER_TEMPLATE = `enable_update_checks = false
enable_auto_update = false

[session_logging]
enabled = true
session_prefix = "session"

[tools.read_file]
max_read_bytes = 64000

[tools.write_file]
max_write_bytes = 64000

[code_server]
enabled = true
port = {{CODE_SERVER_PORT}}
auto_install = true

[[mcp_servers]]
name = "e2e_test_server"
transport = "stdio"
command = "/bin/true"
args = []
`;

export interface ServerConfig {
  port: number;
  token: string;
  codeServerEnabled?: boolean;
  codeServerPort?: number;
}

export class ServerManager {
  private process: child_process.ChildProcess | null = null;
  private config: ServerConfig;
  private started: boolean = false;
  private actualPort: number | null = null;
  private actualCodeServerPort: number | null = null;
  e2eTestDir: string | null = null;
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
      port = await this.findAvailablePort(port);
    }
    this.actualPort = port;

    // Kill any existing process on the port
    await this.killProcessOnPort(port);

    // Reserve code-server port (same pattern as web port)
    if (this.config.codeServerEnabled) {
      let csPort = this.config.codeServerPort ?? (19000 + Math.floor(Math.random() * 100));
      if (!(await this.isPortAvailable(csPort))) {
        csPort = await this.findAvailablePort(csPort);
      }
      this.actualCodeServerPort = csPort;
      await this.killProcessOnPort(csPort);
    }

    // Set up E2E test directory with mock data
    this.e2eTestDir = this.setupE2eTestDir();

    const env = {
      ...process.env,
      VIBE_WEB_TOKEN: this.config.token,
      VIBE_E2E_TEST: "true",
      VIBE_E2E_TEST_DIR: this.e2eTestDir,
      VIBE_HOME: this.e2eTestDir, // Override VIBE_HOME to use E2E test directory
      PYTHONUNBUFFERED: "1",
    };

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
        console.log(
          `[E2E] [${this.actualPort}] pid=${this.process.pid} dir=${this.e2eTestDir}`
        );
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

      // Wait for server to be ready, then optionally wait for code-server
      this.waitForServer()
        .then(() => {
          if (this.config.codeServerEnabled) {
            return this.waitForCodeServer();
          }
          return Promise.resolve();
        })
        .then(() => {
          this.started = true;
          resolve();
        })
        .catch((error) => {
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

    return new Promise((resolve) => {
      this.process?.kill("SIGTERM");

      // Force kill after timeout
      setTimeout(() => {
        this.process?.kill("SIGKILL");
        // Also kill any lingering code-server processes
        if (this.actualCodeServerPort) {
          this.killProcessOnPort(this.actualCodeServerPort).catch(() => {});
        }
        resolve();
      }, 2000);

      this.process?.on("exit", () => {
        this.started = false;
        this.process = null;
        // Kill any lingering code-server processes on cleanup
        if (this.actualCodeServerPort) {
          this.killProcessOnPort(this.actualCodeServerPort).catch(() => {});
        }
        this.cleanupE2eTestDir();
        resolve();
      });
    });
  }

  private waitForServer(): Promise<void> {
    const maxAttempts = 120; // Increased from 60 to 120 (120 seconds total)
    const interval = 1000;

    return new Promise((resolve, reject) => {
      let attempts = 0;

      const check = () => {
        attempts++;
        const req = http.get(
          `http://127.0.0.1:${this.actualPort}/health`,
          (res) => {
            if (res.statusCode === 200) {
              resolve();
            } else {
              if (attempts >= maxAttempts) {
                reject(new Error(`Server returned status ${res.statusCode}`));
              } else {
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

  /**
   * Wait for code-server to become healthy on its port.
   */
  private waitForCodeServer(): Promise<void> {
    const port = this.actualCodeServerPort!;
    const maxAttempts = 60; // 60 seconds
    const interval = 1000;

    return new Promise((resolve, reject) => {
      let attempts = 0;

      const check = () => {
        attempts++;
        const sock = new net.Socket();
        sock.setTimeout(3000);

        sock.on("connect", () => {
          sock.destroy();
          resolve();
        });

        sock.on("error", () => {
          if (attempts >= maxAttempts) {
            reject(new Error(`code-server failed to start on port ${port} after ${maxAttempts}s`));
          } else {
            setTimeout(check, interval);
          }
        });

        sock.on("timeout", () => {
          sock.destroy();
          if (attempts >= maxAttempts) {
            reject(new Error(`code-server health check timeout on port ${port}`));
          } else {
            setTimeout(check, interval);
          }
        });

        sock.connect(port, "127.0.0.1");
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

  getCodeServerPort(): number {
    return this.actualCodeServerPort || 0;
  }

  getCodeServerUrl(): string {
    return `${this.getUrl()}/vscode/`;
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

    // Pre-trust the project directory to avoid trust dialog in E2E tests
    const trustedFoldersFile = path.join(testDir, "trusted_folders.toml");
    fs.writeFileSync(
      trustedFoldersFile,
      `trusted = ["${PROJECT_ROOT}"]\nuntrusted = []\n`,
      "utf-8"
    );

    // Create minimal config.toml without explicit save_dir to allow VIBE_HOME to take effect
    // If save_dir is explicitly set, it overrides SESSION_LOG_DIR path resolution
    const configFile = path.join(testDir, "config.toml");
    let configContent: string;
    if (this.config.codeServerEnabled && this.actualCodeServerPort) {
      configContent = E2E_CONFIG_WITH_CODE_SERVER_TEMPLATE.replace("{{CODE_SERVER_PORT}}", String(this.actualCodeServerPort));
    } else {
      configContent = E2E_CONFIG_TOML;
    }
    fs.writeFileSync(configFile, configContent, "utf-8");

    return testDir;
  }

  /**
   * Clean up E2E test directory.
   */
  private cleanupE2eTestDir(): void {
    if (this.e2eTestDir && fs.existsSync(this.e2eTestDir)) {
      try {
        fs.rmSync(this.e2eTestDir, { recursive: true, force: true });
      } catch (err) {
        console.warn(`Failed to clean up E2E test directory: ${err}`);
      }
    }

    // Clean up PID file
    if (this.serverPidFile && fs.existsSync(this.serverPidFile)) {
      try {
        fs.unlinkSync(this.serverPidFile);
      } catch (err) {
        console.warn(`Failed to clean up PID file: ${err}`);
      }
    }
  }
}
