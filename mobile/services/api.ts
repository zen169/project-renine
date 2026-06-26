import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'renine_jwt_token';
const SERVER_URL_KEY = 'renine_server_url';
const DEFAULT_SERVER_URL = 'https://127.0.0.1:8000'; // Default local address

export class ApiService {
  private static cachedUrl: string | null = null;

  /**
   * Get the configured API server URL.
   */
  static async getServerUrl(): Promise<string> {
    if (this.cachedUrl) {
      return this.cachedUrl;
    }
    const stored = await SecureStore.getItemAsync(SERVER_URL_KEY);
    this.cachedUrl = stored || DEFAULT_SERVER_URL;
    return this.cachedUrl;
  }

  /**
   * Update the configured API server URL.
   */
  static async setServerUrl(url: string): Promise<void> {
    const sanitized = url.replace(/\/+$/, ''); // Strip trailing slash
    await SecureStore.setItemAsync(SERVER_URL_KEY, sanitized);
    this.cachedUrl = sanitized;
  }

  /**
   * Save the JWT token to secure store.
   */
  static async saveToken(token: string): Promise<void> {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  }

  /**
   * Retrieve the stored JWT token.
   */
  static async getToken(): Promise<string | null> {
    return await SecureStore.getItemAsync(TOKEN_KEY);
  }

  /**
   * Clear the stored JWT token.
   */
  static async clearToken(): Promise<void> {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  }

  /**
   * Perform an authenticated API request.
   */
  private static async request(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<any> {
    const baseUrl = await this.getServerUrl();
    const token = await this.getToken();

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Automatic session cleanup on unauthorized
      await this.clearToken();
      throw new Error('Unauthorized');
    }

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Request failed with status ${response.status}`);
    }

    return data;
  }

  /**
   * Perform authentication login call.
   */
  static async login(password: string, username: string = 'admin'): Promise<boolean> {
    const baseUrl = await this.getServerUrl();
    
    // OAuth2PasswordRequestForm expects application/x-www-form-urlencoded
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(`${baseUrl}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Login failed');
    }

    if (data.access_token) {
      await this.saveToken(data.access_token);
      return true;
    }
    return false;
  }

  /**
   * Get server health status.
   */
  static async getHealth(): Promise<any> {
    const baseUrl = await this.getServerUrl();
    const response = await fetch(`${baseUrl}/api/health`);
    return await response.json();
  }

  /**
   * GET /api/memory/context
   */
  static async getMemoryContext(): Promise<any> {
    return await this.request('/api/memory/context');
  }

  /**
   * GET /api/memory/history
   */
  static async getMemoryHistory(limit: number = 20): Promise<any> {
    return await this.request(`/api/memory/history?limit=${limit}`);
  }

  /**
   * GET /api/memory/mind
   */
  static async getMemoryMind(namespace: string, query?: string, limit: number = 50): Promise<any> {
    const params = new URLSearchParams();
    params.append('namespace', namespace);
    if (query) params.append('query', query);
    params.append('limit', limit.toString());
    return await this.request(`/api/memory/mind?${params.toString()}`);
  }

  /**
   * GET /api/memory/personality
   */
  static async getMemoryPersonality(query?: string, limit: number = 50): Promise<any> {
    const params = new URLSearchParams();
    if (query) params.append('query', query);
    params.append('limit', limit.toString());
    return await this.request(`/api/memory/personality?${params.toString()}`);
  }

  /**
   * GET /api/smart-home/devices
   */
  static async getSmartDevices(domain?: string): Promise<any> {
    const path = domain ? `/api/smart-home/devices?domain=${domain}` : '/api/smart-home/devices';
    return await this.request(path);
  }

  /**
   * GET /api/smart-home/devices/{entity_id}
   */
  static async getSmartDeviceState(entityId: string): Promise<any> {
    return await this.request(`/api/smart-home/devices/${entityId}`);
  }

  /**
   * POST /api/smart-home/actions
   */
  static async createSmartHomeAction(entityId: string, service: string): Promise<any> {
    return await this.request('/api/smart-home/actions', {
      method: 'POST',
      body: JSON.stringify({ entity_id: entityId, service }),
    });
  }

  /**
   * POST /api/smart-home/actions/{action_id}/confirm
   */
  static async confirmSmartHomeAction(actionId: number): Promise<any> {
    return await this.request(`/api/smart-home/actions/${actionId}/confirm`, {
      method: 'POST',
    });
  }

  /**
   * GET /api/pets
   */
  static async getPets(): Promise<any> {
    return await this.request('/api/pets');
  }

  /**
   * POST /api/pets/{name}/feed
   */
  static async feedPet(name: string): Promise<any> {
    return await this.request(`/api/pets/${name}/feed`, {
      method: 'POST',
    });
  }

  /**
   * GET /api/reminders
   */
  static async getReminders(): Promise<any> {
    return await this.request('/api/reminders');
  }
}
