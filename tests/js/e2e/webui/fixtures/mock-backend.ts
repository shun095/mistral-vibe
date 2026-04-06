/**
 * Mock backend client for registering mock responses during E2E tests.
 */

export interface MockToolCall {
  id: string;
  name: string;
  arguments: string;
}

export interface MockUsage {
  prompt_tokens: number;
  completion_tokens: number;
}

export interface MockResponse {
  response_text: string;
  tool_calls?: MockToolCall[];
  usage?: MockUsage;
}

export class MockBackendClient {
  private baseUrl: string;
  private authToken: string;

  constructor(baseUrl: string, authToken: string) {
    this.baseUrl = baseUrl;
    this.authToken = authToken;
  }

  /**
   * Register a mock response that will be returned by the fake backend.
   */
  async registerResponse(mock: MockResponse): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/test/mock-data`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Cookie: `vibe_auth=${this.authToken}`,
      },
      body: JSON.stringify(mock),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `Failed to register mock response: ${response.status} ${errorText}`
      );
    }

    const data = await response.json();
    if (!data.success) {
      throw new Error(`Mock registration failed: ${data.message}`);
    }
  }

  /**
   * Reset the mock data store (clear all registered responses).
   */
  async reset(): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/test/mock-data/reset`, {
      method: "POST",
      headers: {
        Cookie: `vibe_auth=${this.authToken}`,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to reset mock data: ${response.status} ${errorText}`);
    }

    const data = await response.json();
    if (!data.success) {
      throw new Error(`Mock reset failed: ${data.message}`);
    }
  }

  /**
   * Get usage statistics for the mock data store.
   */
  async getUsage(): Promise<{
    registered: number;
    consumed: number;
    remaining: number;
  }> {
    const response = await fetch(`${this.baseUrl}/api/test/mock-data/usage`, {
      headers: {
        Cookie: `vibe_auth=${this.authToken}`,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to get mock usage: ${response.status} ${errorText}`);
    }

    const data = await response.json();
    return data.usage;
  }

  /**
   * Register a tool call response.
   */
  async registerToolCall(
    toolName: string,
    argumentsJson: string,
    toolId?: string
  ): Promise<void> {
    await this.registerResponse({
      response_text: "",
      tool_calls: [
        {
          id: toolId || `call_${Date.now()}`,
          name: toolName,
          arguments: argumentsJson,
        },
      ],
    });
  }
}
