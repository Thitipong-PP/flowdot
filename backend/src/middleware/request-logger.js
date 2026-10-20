import { randomUUID } from 'node:crypto';
import { appendFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const logDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../.data/logs');

export function requestLogger(req, res, next) {
  const requestId = randomUUID();
  const startedAt = process.hrtime.bigint();
  req.requestId = requestId;
  res.setHeader('x-request-id', requestId);
  res.once('finish', () => {
    const status = res.statusCode;
    const record = {
      timestamp: new Date().toISOString(),
      level: status >= 500 ? 'error' : status >= 400 ? 'warn' : 'info',
      event: 'http_request',
      requestId,
      method: req.method,
      path: req.path,
      status,
      durationMs: Number(process.hrtime.bigint() - startedAt) / 1e6,
      ...(req.auth ? { actorRole: req.auth.role } : {}),
      ...(req.logError ? { errorType: req.logError.type, ...(req.logError.code ? { errorCode: req.logError.code } : {}) } : {}),
    };
    const line = `${JSON.stringify(record)}\n`;
    if (status >= 500) process.stderr.write(line);
    else process.stdout.write(line);
    const filename = path.join(logDirectory, `${new Date().toISOString().slice(0, 10)}.jsonl`);
    void mkdir(logDirectory, { recursive: true })
      .then(() => appendFile(filename, line, { mode: 0o600 }))
      .catch((error) => process.stderr.write(`${JSON.stringify({ level: 'error', event: 'log_write_failed', message: error.message })}\n`));
  });
  next();
}
