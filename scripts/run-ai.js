import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const isWin = process.platform === 'win32';
const venvPython = isWin
  ? resolve('AI', '.venv', 'Scripts', 'python.exe')
  : resolve('AI', '.venv', 'bin', 'python');

const pythonExe = existsSync(venvPython) ? venvPython : (isWin ? 'python' : 'python3');

if (!existsSync(venvPython)) {
  console.warn('\x1b[33m%s\x1b[0m', '[AI Service Warning] Virtual environment "AI/.venv" not found. Using system python.');
  console.warn('\x1b[33m%s\x1b[0m', 'If packages are missing, set it up with:');
  console.warn('\x1b[33m%s\x1b[0m', '  python -m venv AI/.venv && .\\AI\\.venv\\Scripts\\pip install -r AI/requirements.txt\n');
}

const child = spawn(
  pythonExe,
  ['-m', 'uvicorn', 'app.main:app', '--app-dir', 'AI', '--host', '127.0.0.1', '--port', '8000'],
  {
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
  console.error('\x1b[31m%s\x1b[0m', `[AI Service Failed to start]: ${err.message}`);
  process.exit(1);
});

child.on('close', (code) => {
  process.exit(code ?? 0);
});
