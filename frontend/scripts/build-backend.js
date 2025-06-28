#!/usr/bin/env node
/**
 * Cross-platform backend builder script.
 * Steps:
 * 1. Ensure Python 3.12 (or python fallback) available.
 * 2. Create virtual environment in ../backend/.venv if missing.
 * 3. Install requirements.
 * 4. Run pyinstaller with given arguments.
 *
 * Works in PowerShell, CMD, Bash, Zsh because logic is inside Node.
 */
const { spawn } = require('child_process');
const fs = require('fs');
const fsp = fs.promises;
const path = require('path');

const repoRoot = path.resolve(__dirname, '..', '..');
const backendDir = path.join(repoRoot, 'backend');
const venvDir = path.join(backendDir, 'venv');
const isWin = process.platform === 'win32';

const PYTHON_CANDIDATES = isWin
  ? ['python', 'python3', 'python3.12', 'py -3.12', 'py -3']
  : ['python3', 'python','python3.12'];

function run(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: 'inherit', shell: true, ...opts });
    child.on('exit', code => {
      if (code === 0) resolve(); else reject(new Error(`Command failed: ${cmd} ${args.join(' ')} (code ${code})`));
    });
    child.on('error', reject);
  });
}

async function findPython() {
  const tried = [];
  const semverOk = (text) => {
    const m = text.match(/Python\s+(\d+)\.(\d+)\.(\d+)/i);
    if (!m) return false;
    const major = parseInt(m[1], 10); const minor = parseInt(m[2], 10);
    return major === 3 && minor >= 12; // require 3.12+
  };
  for (const candidate of PYTHON_CANDIDATES) {
    try {
      const versionText = await new Promise((resolve, reject) => {
        const child = spawn(candidate, ['--version'], { shell: true });
        let out = '';
        child.stdout && child.stdout.on('data', d => out += d.toString());
        child.stderr && child.stderr.on('data', d => out += d.toString());
        child.on('error', reject);
        child.on('exit', code => code === 0 ? resolve(out.trim()) : reject(new Error('exit '+code)));
      });
      tried.push(`${candidate} => ${versionText}`);
      if (semverOk(versionText)) {
        console.log(`Using Python interpreter: ${candidate} (${versionText})`);
        return candidate;
      } else {
        console.log(`Rejecting ${candidate} (needs 3.12+, got ${versionText})`);
      }
    } catch (e) {
      tried.push(`${candidate} => not usable (${e.message})`);
    }
  }
  throw new Error('Python 3.12+ not found. Attempts:\n' + tried.join('\n'));
}

async function ensureVenv(pythonExe) {
  const marker = path.join(venvDir, 'pyvenv.cfg');
  if (fs.existsSync(marker)) {
    return; // venv exists
  }
  console.log('Creating virtual environment...');
  await fsp.mkdir(venvDir, { recursive: true });
  await run(pythonExe, ['-m', 'venv', venvDir]);
}

function venvPython() {
  return isWin ? path.join(venvDir, 'Scripts', 'python.exe') : path.join(venvDir, 'bin', 'python');
}

async function pipInstall(requirementsFile) {
  const py = venvPython();
  await run(py, ['-m', 'pip', 'install', '--upgrade', 'pip']);
  await run(py, ['-m', 'pip', 'install', '-r', requirementsFile]);
}

async function buildBackend() {
  const requirementsFile = path.join(backendDir, 'requirements.txt');
  if (!fs.existsSync(requirementsFile)) {
    throw new Error('requirements.txt not found in backend directory');
  }

  const pythonExe = await findPython();
  await ensureVenv(pythonExe);

  console.log('Installing dependencies...');
  await pipInstall(requirementsFile);

  console.log('Running PyInstaller...');
  const py = venvPython();
  const pyInstallerCmd = [
    '-m', 'PyInstaller',
    '--name', 'backend',
    '--clean',
    '--onedir',
    '--console',
    `--paths=backend`,
    '--add-data', 'backend/data;data',
    '--add-data', 'backend/app/prompting/jinja_templates;jinja',
    '--hidden-import', 'jinja2',
    '--hidden-import', 'sqlalchemy',
    '--hidden-import', 'backend.app.secrets',
    'run.py'
  ];
  await run(py, pyInstallerCmd, { cwd: repoRoot });
  console.log('Backend build complete. Output in dist/backend');
}

buildBackend().catch(err => {
  console.error('\n[BACKEND BUILD ERROR]', err.message);
  process.exit(1);
});
