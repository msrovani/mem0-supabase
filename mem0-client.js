/**
 * Mem0 JavaScript/TypeScript Client — Official SDK for the Mem0 Memory API.
 *
 * Usage:
 *   import { Mem0Client } from './mem0-client.js';
 *
 *   const client = new Mem0Client({
 *     baseUrl: 'http://localhost:8000',
 *     apiKey: 'your-jwt-token',
 *   });
 *
 *   // Create memories
 *   const result = await client.add('User likes pizza', { userId: 'user1' });
 *
 *   // Search
 *   const results = await client.search('food preferences', { userId: 'user1' });
 *
 *   // Get all
 *   const memories = await client.getAll({ userId: 'user1' });
 */

class Mem0Error extends Error {
  constructor(message, statusCode, response) {
    super(message);
    this.name = 'Mem0Error';
    this.statusCode = statusCode;
    this.response = response;
  }
}

class Mem0Client {
  /**
   * @param {Object} options
   * @param {string} [options.baseUrl='http://localhost:8000']
   * @param {string} [options.apiKey]
   * @param {number} [options.timeout=30000]
   * @param {number} [options.retries=3]
   */
  constructor({ baseUrl = 'http://localhost:8000', apiKey, timeout = 30000, retries = 3 } = {}) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.apiKey = apiKey;
    this.timeout = timeout;
    this.retries = retries;
  }

  /** @private */
  async _request(method, path, data) {
    const url = `${this.baseUrl}${path}`;
    const headers = { 'Content-Type': 'application/json', Accept: 'application/json' };
    if (this.apiKey) headers['Authorization'] = `Bearer ${this.apiKey}`;

    let lastError;
    for (let attempt = 0; attempt <= this.retries; attempt++) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout);

        const response = await fetch(url, {
          method,
          headers,
          body: data ? JSON.stringify(data) : undefined,
          signal: controller.signal,
        });
        clearTimeout(timer);

        if (!response.ok) {
          const error = await response.json().catch(() => ({}));
          throw new Mem0Error(error.error || error.detail || `HTTP ${response.status}`, response.status, error);
        }

        const text = await response.text();
        return text ? JSON.parse(text) : {};
      } catch (err) {
        lastError = err;
        if (err.name === 'AbortError') {
          lastError = new Mem0Error('Request timeout', 408);
        }
        if (attempt < this.retries) {
          await new Promise((r) => setTimeout(r, Math.pow(2, attempt) * 500));
        }
      }
    }
    throw lastError;
  }

  /**
   * Add a memory.
   * @param {string|Array<{role:string,content:string}>} messages
   * @param {Object} [options]
   * @param {string} [options.userId]
   * @param {string} [options.agentId]
   * @param {string} [options.runId]
   * @param {Object} [options.metadata]
   * @param {string} [options.idempotencyKey]
   */
  async add(messages, { userId, agentId, runId, metadata, idempotencyKey } = {}) {
    const msgs = typeof messages === 'string' ? [{ role: 'user', content: messages }] : messages;
    return this._request('POST', '/memories', {
      messages: msgs, user_id: userId, agent_id: agentId, run_id: runId, metadata, idempotency_key: idempotencyKey,
    });
  }

  /**
   * Search memories.
   * @param {string} query
   * @param {Object} [options]
   */
  async search(query, { userId, agentId, runId, filters } = {}) {
    return this._request('POST', '/search', { query, user_id: userId, agent_id: agentId, run_id: runId, filters });
  }

  /**
   * Get all memories.
   */
  async getAll({ userId, agentId, runId, cursor, limit = 20 } = {}) {
    const params = new URLSearchParams();
    if (userId) params.set('user_id', userId);
    if (agentId) params.set('agent_id', agentId);
    if (runId) params.set('run_id', runId);
    if (cursor) params.set('cursor', cursor);
    params.set('limit', String(limit));
    return this._request('GET', `/memories?${params}`);
  }

  /** Get a specific memory. */
  async get(memoryId) { return this._request('GET', `/memories/${memoryId}`); }

  /** Update a memory. */
  async update(memoryId, data) { return this._request('PUT', `/memories/${memoryId}`, data); }

  /** Delete a memory. */
  async delete(memoryId) { return this._request('DELETE', `/memories/${memoryId}`); }

  /** Delete all memories for an identifier. */
  async deleteAll({ userId, agentId, runId } = {}) {
    const params = new URLSearchParams();
    if (userId) params.set('user_id', userId);
    if (agentId) params.set('agent_id', agentId);
    if (runId) params.set('run_id', runId);
    return this._request('DELETE', `/memories?${params}`);
  }

  /** Reset all memories. */
  async reset() { return this._request('POST', '/reset'); }

  /** Health check. */
  async health() { return this._request('GET', '/health'); }

  /** Bulk add memories. */
  async bulkAdd(items) { return this._request('POST', '/memories/bulk', { items }); }
}

if (typeof module !== 'undefined') module.exports = { Mem0Client, Mem0Error };
