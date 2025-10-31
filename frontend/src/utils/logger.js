/**
 * Logger utility for frontend
 * Uses debug pattern in development, structured logging in production
 * Replaces console.log calls with scoped, named logging
 *
 * @usage
 * const log = createLogger("ComponentName");
 * log("Message"); // Logs: ComponentName Message
 * log.warn("Warning"); // Logs: ComponentName Warning
 * log.error("Error"); // Logs: ComponentName Error
 */
/* eslint-disable no-console */

const IS_DEV = process.env.NODE_ENV === "development";

/**
 * Create a scoped logger with namespace
 * @param {string} namespace - Component or module name
 * @returns {Object} Logger object with log, warn, error, debug methods
 */
export function createLogger(namespace) {
  const prefix = `[${namespace}]`;

  return {
    /**
     * Log a message
     * @param {string} message - Message to log
     * @param {*} data - Optional data to include
     */
    log(message, data) {
      if (IS_DEV) {
        if (data !== undefined) {
          console.log(`${prefix} ${message}`, data);
        } else {
          console.log(`${prefix} ${message}`);
        }
      }
    },

    /**
     * Log a warning
     * @param {string} message - Warning message
     * @param {*} data - Optional data to include
     */
    warn(message, data) {
      if (data !== undefined) {
        console.warn(`${prefix} ${message}`, data);
      } else {
        console.warn(`${prefix} ${message}`);
      }
    },

    /**
     * Log an error
     * @param {string} message - Error message
     * @param {Error|*} error - Error object or data
     */
    error(message, error) {
      if (error !== undefined) {
        console.error(`${prefix} ${message}`, error);
      } else {
        console.error(`${prefix} ${message}`);
      }
    },

    /**
     * Log debug information (dev only)
     * @param {string} message - Debug message
     * @param {*} data - Optional data to include
     */
    debug(message, data) {
      if (IS_DEV) {
        if (data !== undefined) {
          console.debug(`${prefix} ${message}`, data);
        } else {
          console.debug(`${prefix} ${message}`);
        }
      }
    },
  };
}

/**
 * Global logger for utility functions without component context
 */
export const log = createLogger("Erudi");
