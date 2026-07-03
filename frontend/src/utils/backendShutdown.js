// Graceful backend shutdown (#216).
//
// Every close path used to hard-kill the backend (taskkill /F /T on Windows),
// so the FastAPI lifespan shutdown never ran: the embedded Postgres postmaster
// detached and survived as an orphan holding its data dir, and every next boot
// paid WAL recovery. Instead we close the backend's stdin — the launcher
// (run.py, opt-in via ERUDI_WATCH_STDIN) watches for that EOF and asks uvicorn
// to shut down cleanly (checkpointer close, stop_postgres). We wait up to
// timeoutMs for the child to exit on its own, then fall back to the hard
// tree-kill so a wedged backend can never block quit. POSIX was already
// graceful (SIGTERM relay in run.py); this closes the Windows gap without a
// second code path.

const DEFAULT_TIMEOUT_MS = 8000;

/**
 * Ask the backend to exit cleanly, falling back to a hard kill on timeout.
 *
 * @param {object}   proc         backend child process (or null)
 * @param {object}   [opts]
 * @param {number}   [opts.timeoutMs=8000] grace period before the hard kill
 * @param {function} [opts.killFn] (proc) => void hard tree-kill fallback
 * @returns {Promise<"graceful"|"forced"|"noop">}
 *   "noop" (no process), "graceful" (exited on its own within budget), or
 *   "forced" (timed out, hard-killed).
 */
export function gracefulShutdown(proc, { timeoutMs = DEFAULT_TIMEOUT_MS, killFn } = {}) {
  return new Promise((resolve) => {
    if (!proc) {
      resolve("noop");
      return;
    }
    // Already exited: nothing to wait for and nothing to kill.
    if (proc.exitCode !== null && proc.exitCode !== undefined) {
      resolve("graceful");
      return;
    }

    let settled = false;
    let timer = null;
    const finish = (outcome) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      resolve(outcome);
    };

    // Attach before touching stdin so we can never miss the exit event.
    proc.once("exit", () => finish("graceful"));

    // Close stdin: this is the EOF the launcher's watcher turns into a clean
    // uvicorn shutdown. Guarded — stdin may already be closed/destroyed.
    try {
      if (proc.stdin) proc.stdin.end();
    } catch (_) {
      // The timeout below still protects us if closing stdin fails.
    }

    timer = setTimeout(() => {
      try {
        if (killFn) killFn(proc);
      } catch (_) {
        // Best effort: resolve regardless so quit never hangs on a hung kill.
      }
      finish("forced");
    }, timeoutMs);
  });
}
