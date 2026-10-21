import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const isWin = process.platform === 'win32';
const venvPython = isWin
  ? resolve('AI', '.venv', 'Scripts', 'python.exe')
  : resolve('AI', '.venv', 'bin', 'python');

const pythonExe = existsSync(venvPython) ? venvPython : (isWin ? 'python' : 'python3');

if (!existsSync(venvPython)) {
  console.warn('\x1b[33m%s\x1b[0m', '[AI Seeder Warning] Virtual environment "AI/.venv" not found. Using system python.');
}

const child = spawn(
  pythonExe,
  ['-m', 'app.db.seed_loan_catalog'],
  {
    cwd: resolve('AI'),
    stdio: 'inherit',
    shell: false,
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
    },
  }
);

child.on('error', (err) => {
  console.error('\x1b[31m%s\x1b[0m', `[AI Seeder Failed]: ${err.message}`);
  process.exit(1);
});

child.on('close', (code) => {
  process.exit(code ?? 0);
});
