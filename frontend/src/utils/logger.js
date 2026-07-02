/**
 * Logger utility for frontend
 * Console behavior: log/debug are dev-only, warn/error always print.
 * File persistence: EVERY call (log/info, warn, error — debug in dev only) is
 * additionally forwarded, fire-and-forget, to the main process through the
 * window.logAPI preload bridge when it exists, so renderer logs land in the
 * shared log file (os.tmpdir()/erudi-backend.log) even in production builds.
 *
 * @usage
 * const log = createLogger("ComponentName");
 * log.log("Message"); // Logs: [ComponentName] Message
 * log.warn("Warning"); // Logs: [ComponentName] Warning
 * log.error("Error"); // Logs: [ComponentName] Error
 */
/* eslint-disable no-console */

const IS_DEV = process.env.NODE_ENV === "development";
const FORWARD_DATA_MAX_CHARS = 2000;

/**
 * Serialize arbitrary data for the log bridge: JSON when possible, truncated,
 * and guaranteed to never throw.
 * @param {*} data - Anything a call site attached to the log call.
 * @param {number} limit - Max serialized length before truncation.
 * @returns {string|undefined} Serialized data, or undefined when absent.
 */
function safeJson(data, limit = FORWARD_DATA_MAX_CHARS) {
  if (data === undefined) return undefined;
  try {
    let text;
    if (typeof data === "string") {
      text = data;
    } else if (data instanceof Error) {
      text = `${data.name}: ${data.message}`;
    } else {
      text = JSON.stringify(data);
    }
    if (typeof text !== "string") text = String(text);
    if (text.length > limit) return `${text.slice(0, limit)}… [+${text.length - limit}]`;
    return text;
  } catch {
    try {
      return String(data).slice(0, limit);
    } catch {
      return "[unserializable]";
    }
  }
}

/**
 * Forward one entry to the main-process log file through the preload bridge
 * (fire-and-forget ipcRenderer.send). No bridge (tests, plain browser, main
 * process) → silent no-op. Never throws.
 */
function forwardToMain(level, namespace, message, data) {
  try {
    const bridge = typeof window !== "undefined" ? window.logAPI : undefined;
    if (!bridge || typeof bridge.send !== "function") return;
    bridge.send({
      ts: new Date().toISOString(),
      level,
      ns: namespace,
      msg: String(message),
      data: safeJson(data),
    });
  } catch {
    // Logging must never break the app.
  }
}

/**
 * Create a scoped logger with namespace
 * @param {string} namespace - Component or module name
 * @returns {Object} Logger object with log, info, warn, error, debug methods
 */
export function createLogger(namespace) {
  const prefix = `[${namespace}]`;

  const emitConsole = (method, message, data) => {
    if (data !== undefined) {
      console[method](`${prefix} ${message}`, data);
    } else {
      console[method](`${prefix} ${message}`);
    }
  };

  /**
   * Info-level log. Console output stays dev-only, but the entry is always
   * forwarded to the log file — that's the production persistence path.
   * @param {string} message - Message to log
   * @param {*} data - Optional data to include
   */
  const info = (message, data) => {
    if (IS_DEV) emitConsole("log", message, data);
    forwardToMain("info", namespace, message, data);
  };

  return {
    log: info,

    /** Explicit alias of log() — same info level. */
    info,

    /**
     * Log a warning
     * @param {string} message - Warning message
     * @param {*} data - Optional data to include
     */
    warn(message, data) {
      emitConsole("warn", message, data);
      forwardToMain("warn", namespace, message, data);
    },

    /**
     * Log an error
     * @param {string} message - Error message
     * @param {Error|*} error - Error object or data
     */
    error(message, error) {
      emitConsole("error", message, error);
      forwardToMain("error", namespace, message, error);
    },

    /**
     * Log debug information (dev only, console and file alike)
     * @param {string} message - Debug message
     * @param {*} data - Optional data to include
     */
    debug(message, data) {
      if (!IS_DEV) return;
      emitConsole("debug", message, data);
      forwardToMain("debug", namespace, message, data);
    },
  };
}

/**
 * Global logger for utility functions without component context
 */
export const log = createLogger("Erudi");
