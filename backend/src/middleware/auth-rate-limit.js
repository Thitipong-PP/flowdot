import { HttpError } from '../utils/http-error.js';

const attempts = new Map();
const WINDOW_MS = 15 * 60 * 1000;
const MAX_ATTEMPTS = 10;

export function authRateLimit(req, _res, next) {
  const now = Date.now();
  const key = req.ip ?? 'unknown';
  const entry = attempts.get(key);
  const current = !entry || entry.resetAt <= now ? { count: 0, resetAt: now + WINDOW_MS } : entry;
  current.count += 1;
  attempts.set(key, current);
  if (attempts.size > 5000) {
    for (const [ip, item] of attempts) if (item.resetAt <= now) attempts.delete(ip);
  }
  if (current.count > MAX_ATTEMPTS) return next(new HttpError(429, 'Too many sign-in attempts. Please try again later.'));
  return next();
}
