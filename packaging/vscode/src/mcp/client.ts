/**
 * NetCheck MCP Client
 *
 * JSON-RPC 2.0 client that communicates with the netcheck MCP server
 * running as a child process over stdio.
 */

import { ChildProcess, spawn } from "child_process";
import * as vscode from "vscode";

export interface McpTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface McpCallResult {
  content: Array<{ type: string; text: string }>;
  isError?: boolean;
}

export interface McpError {
  code: number;
  message: string;
  data?: unknown;
}

export class McpClient {
  private process: ChildProcess | null = null;
  private buffer = "";
  private pendingRequests = new Map<
    number,
    { resolve: (v: unknown) => void; reject: (e: Error) => void }
  >();
  private nextId = 1;
  private initialized = false;
  private tools: McpTool[] = [];

  constructor(private readonly pythonPath: string) {}

  // ── Lifecycle ──────────────────────────────────────────────────────────

  async start(): Promise<void> {
    if (this.process) {
      return; // already running
    }

    this.process = spawn(this.pythonPath, ["-m", "netcheck", "mcp"], {
      stdio: ["pipe", "pipe", "pipe"],
    });

    this.process.stdout?.setEncoding("utf8");
    this.process.stdout?.on("data", (chunk: string) => this.onData(chunk));

    this.process.stderr?.setEncoding("utf8");
    this.process.stderr?.on("data", (chunk: string) => {
      console.error("[NetCheck MCP stderr]", chunk.trim());
    });

    this.process.on("exit", (code) => {
      console.log(`[NetCheck MCP] process exited with code ${code}`);
      this.process = null;
      this.initialized = false;
      this.pendingRequests.forEach(({ reject }) =>
        reject(new Error("MCP server process exited unexpectedly"))
      );
      this.pendingRequests.clear();
    });

    await this.initialize();
  }

  async stop(): Promise<void> {
    if (this.process) {
      this.process.kill("SIGTERM");
      this.process = null;
    }
    this.initialized = false;
    this.pendingRequests.clear();
  }

  async restart(): Promise<void> {
    await this.stop();
    await this.start();
  }

  get isRunning(): boolean {
    return this.process !== null;
  }

  // ── MCP Protocol ──────────────────────────────────────────────────────

  private async initialize(): Promise<void> {
    const result = (await this.sendRequest("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "vscode-netcheck", version: "2.5.0" },
    })) as { protocolVersion: string };

    if (!result?.protocolVersion) {
      throw new Error("MCP initialize did not return protocolVersion");
    }

    await this.sendNotification("notifications/initialized", {});
    this.initialized = true;
    this.tools = await this.listTools();
  }

  async listTools(): Promise<McpTool[]> {
    const result = (await this.sendRequest("tools/list", {})) as {
      tools: McpTool[];
    };
    return result?.tools ?? [];
  }

  async callTool(
    name: string,
    args: Record<string, unknown>
  ): Promise<McpCallResult> {
    if (!this.initialized) {
      throw new Error("MCP client not initialized. Call start() first.");
    }
    const result = await this.sendRequest("tools/call", {
      name,
      arguments: args,
    });
    return result as McpCallResult;
  }

  getTools(): McpTool[] {
    return this.tools;
  }

  // ── JSON-RPC Transport ────────────────────────────────────────────────

  private sendRequest(method: string, params: unknown): Promise<unknown> {
    return new Promise((resolve, reject) => {
      if (!this.process?.stdin) {
        reject(new Error("MCP server process not running"));
        return;
      }
      const id = this.nextId++;
      const message = JSON.stringify({ jsonrpc: "2.0", id, method, params });
      this.pendingRequests.set(id, { resolve, reject });
      this.process.stdin.write(message + "\n");

      // 30-second timeout per request
      setTimeout(() => {
        if (this.pendingRequests.has(id)) {
          this.pendingRequests.delete(id);
          reject(new Error(`MCP request '${method}' timed out after 30s`));
        }
      }, 30_000);
    });
  }

  private sendNotification(method: string, params: unknown): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.process?.stdin) {
        reject(new Error("MCP server process not running"));
        return;
      }
      const message = JSON.stringify({ jsonrpc: "2.0", method, params });
      this.process.stdin.write(message + "\n");
      resolve();
    });
  }

  private onData(chunk: string): void {
    this.buffer += chunk;
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const msg = JSON.parse(trimmed) as {
          id?: number;
          result?: unknown;
          error?: McpError;
        };
        if (msg.id !== undefined) {
          const pending = this.pendingRequests.get(msg.id);
          if (pending) {
            this.pendingRequests.delete(msg.id);
            if (msg.error) {
              pending.reject(
                new Error(`MCP error ${msg.error.code}: ${msg.error.message}`)
              );
            } else {
              pending.resolve(msg.result);
            }
          }
        }
      } catch (e) {
        console.error("[NetCheck MCP] Failed to parse message:", trimmed);
      }
    }
  }
}

// Singleton instance per extension context
let _client: McpClient | null = null;

export function getClient(context: vscode.ExtensionContext): McpClient {
  if (!_client) {
    const config = vscode.workspace.getConfiguration("netcheck");
    const pythonPath = config.get<string>("pythonPath", "python");
    _client = new McpClient(pythonPath);
    context.subscriptions.push({ dispose: () => _client?.stop() });
  }
  return _client;
}

export function resetClient(): void {
  _client = null;
}
