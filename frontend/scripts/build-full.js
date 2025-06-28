#!/usr/bin/env node
// Cross-shell build orchestrator: runs backend then frontend (make) sequentially.
const { spawn } = require('child_process');
const { runInContext } = require('vm');

function run(cmd, args, opts={}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: 'inherit', shell: true, ...opts });
    child.on('exit', code => code === 0 ? resolve() : reject(new Error(`${cmd} ${args.join(' ')} exited with code ${code}`)));
    child.on('error', reject);
  });
}

(async () => {
  try {
    await run('npm', ['install']);
    await run('npm', ['run', 'backend']);
    await run('npm', ['run', 'frontend']);
  } catch (e) {
    console.error('[BUILD-FULL ERROR]', e.message);
    process.exit(1);
  }
})();
