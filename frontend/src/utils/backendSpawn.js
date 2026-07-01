// Spawn options for the backend child process (#142).
//
// The Windows backend is a console-subsystem PyInstaller exe (backend.spec:
// console=True, kept so Electron can read the stdout JSON lifecycle events).
// Without windowsHide, Windows allocates a console window for it — an empty
// window that flashes on launch and again briefly whenever the backend crashes.
// stdout still flows through the piped stdio, so hiding the window costs nothing
// (a visible console is NOT required to capture stdout).
//
// `detached` is POSIX-only: killBackend tears the whole tree down with
// kill(-pid) there, but on Windows it uses `taskkill /F /T`, so detaching is
// unnecessary and only contributes the console window.

/**
 * Build the child_process.spawn options for the backend.
 * @param {string} platform - process.platform ("win32" | "darwin" | "linux")
 * @param {{ cwd: string, env: object }} io - working dir + environment
 * @returns {object} spawn options
 */
export function buildBackendSpawnOptions(platform, { cwd, env }) {
  const isWin = platform === "win32";
  return {
    stdio: ["pipe", "pipe", "pipe"],
    cwd,
    env,
    // POSIX: own process group so killBackend can kill(-pid) the tree.
    detached: !isWin,
    // Windows: suppress the console-subsystem window; no-op elsewhere.
    windowsHide: true,
  };
}
