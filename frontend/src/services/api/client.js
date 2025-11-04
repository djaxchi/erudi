import { createLogger } from "../../utils/logger";
import { API_BASE_URL } from "../../config/api";

const log = createLogger("APIClient");

/**
 * API client with built-in retry logic, timeout handling, and error normalization
 * Provides consistent error handling and response transformation across the app
 */
class APIClient {
  constructor(baseURL = API_BASE_URL) {
    this.baseURL = baseURL;
    this.timeout = 30000; // 30 seconds
    this.maxRetries = 3;
    this.retryDelay = 1000; // 1 second, will exponentially backoff
  }

  /**
   * Make a GET request
   * @param {string} endpoint - Relative endpoint path
   * @param {Object} options - Request options (headers, params, etc)
   * @returns {Promise<*>} Parsed response data
   */
  async get(endpoint, options = {}) {
    return this.request(endpoint, { method: "GET", ...options });
  }

  /**
   * Make a POST request
   * @param {string} endpoint - Relative endpoint path
   * @param {Object} data - Request body data
   * @param {Object} options - Request options
   * @returns {Promise<*>} Parsed response data
   */
  async post(endpoint, data = {}, options = {}) {
    return this.request(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
      ...options,
    });
  }

  /**
   * Make a PUT request
   * @param {string} endpoint - Relative endpoint path
   * @param {Object} data - Request body data
   * @param {Object} options - Request options
   * @returns {Promise<*>} Parsed response data
   */
  async put(endpoint, data = {}, options = {}) {
    return this.request(endpoint, {
      method: "PUT",
      body: JSON.stringify(data),
      ...options,
    });
  }

  /**
   * Make a PATCH request
   * @param {string} endpoint - Relative endpoint path
   * @param {Object} data - Request body data
   * @param {Object} options - Request options
   * @returns {Promise<*>} Parsed response data
   */
  async patch(endpoint, data = {}, options = {}) {
    return this.request(endpoint, {
      method: "PATCH",
      body: JSON.stringify(data),
      ...options,
    });
  }

  /**
   * Make a DELETE request
   * @param {string} endpoint - Relative endpoint path
   * @param {Object} options - Request options
   * @returns {Promise<*>} Parsed response data
   */
  async delete(endpoint, options = {}) {
    return this.request(endpoint, { method: "DELETE", ...options });
  }

  /**
   * Core request method with retry logic and error handling
   * @private
   * @param {string} endpoint - API endpoint
   * @param {Object} options - Fetch options
   * @param {number} attempt - Current attempt number
   * @returns {Promise<*>} Parsed response
   */
  async request(endpoint, options = {}, attempt = 1) {
    const url = `${this.baseURL}${endpoint}`;
    const controller = new AbortController();

    try {
      // Set timeout
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);

      const headers = {
        "Content-Type": "application/json",
        ...options.headers,
      };

      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Handle non-OK responses
      if (!response.ok) {
        const error = await this.handleErrorResponse(response);
        throw error;
      }

      // Parse and return response
      try {
        const data = await response.json();
        return data;
      } catch {
        // If response is not JSON, return response object
        return response;
      }
    } catch (error) {
      // Handle timeout
      if (error.name === "AbortError") {
        const timeoutError = new Error("Request timeout");
        timeoutError.code = "TIMEOUT";
        throw timeoutError;
      }

      // Retry on transient errors
      if (this.isTransientError(error) && attempt < this.maxRetries) {
        const delay = this.retryDelay * Math.pow(2, attempt - 1); // Exponential backoff
        log.warn(`Request failed, retrying in ${delay}ms (attempt ${attempt}/${this.maxRetries})`);
        await this.sleep(delay);
        return this.request(endpoint, options, attempt + 1);
      }

      throw error;
    }
  }

  /**
   * Handle error responses from API
   * @private
   * @param {Response} response - Fetch Response object
   * @returns {Promise<Error>} Normalized error
   */
  async handleErrorResponse(response) {
    let errorData = {};
    try {
      errorData = await response.json();
    } catch {
      // If response is not JSON, use status text
      errorData = { detail: response.statusText };
    }

    const error = new Error(
      errorData.detail || errorData.message || `API Error: ${response.status}`
    );
    error.status = response.status;
    error.code = `HTTP_${response.status}`;
    error.data = errorData;

    return error;
  }

  /**
   * Check if error is transient and should be retried
   * @private
   * @param {Error} error - Error object
   * @returns {boolean} Whether error is transient
   */
  isTransientError(error) {
    // Network errors are transient
    if (error instanceof TypeError && error.message.includes("fetch")) {
      return true;
    }

    // Specific error codes that are transient
    const transientCodes = ["ECONNREFUSED", "ENOTFOUND", "ETIMEDOUT", "EHOSTUNREACH"];
    if (transientCodes.includes(error.code)) {
      return true;
    }

    return false;
  }

  /**
   * Sleep utility for delays
   * @private
   * @param {number} ms - Milliseconds to sleep
   * @returns {Promise<void>}
   */
  sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// Export singleton instance
export const apiClient = new APIClient();

export default apiClient;
