import { createHmac, randomBytes, scrypt as scryptCallback, timingSafeEqual } from 'node:crypto';
import { promisify } from 'node:util';
import { env } from '../config/env.js';

const scrypt = promisify(scryptCallback);
const TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7;

export async function hashPassword(password) {
  const salt = randomBytes(16).toString('hex');
  const derivedKey = await scrypt(password, salt, 64);
  return `${salt}:${derivedKey.toString('hex')}`;
}

export async function verifyPassword(password, storedHash) {
  if (typeof storedHash !== 'string' || !storedHash.includes(':')) return false;
  const [salt, hash] = storedHash.split(':');
  const expected = Buffer.from(hash, 'hex');
  const actual = await scrypt(password, salt, expected.length);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

function sign(value) {
  return createHmac('sha256', env.authSecret).update(value).digest('base64url');
}

export function createSessionToken(account) {
  const now = Math.floor(Date.now() / 1000);
  const payload = Buffer.from(JSON.stringify({
    sub: account.id,
    customerId: account.customerId?.toString() ?? null,
    role: account.role,
    sessionVersion: account.sessionVersion ?? 0,
    iat: now,
    exp: now + TOKEN_TTL_SECONDS,
  })).toString('base64url');
  const unsigned = `v1.${payload}`;
  return `${unsigned}.${sign(unsigned)}`;
}

export function verifySessionToken(token) {
  const [version, payload, signature, extra] = token.split('.');
  if (version !== 'v1' || !payload || !signature || extra) return null;
  const unsigned = `${version}.${payload}`;
  const expected = Buffer.from(sign(unsigned));
  const actual = Buffer.from(signature);
  if (expected.length !== actual.length || !timingSafeEqual(expected, actual)) return null;
  try {
    const decoded = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    if (!decoded.sub || !decoded.exp || decoded.exp <= Math.floor(Date.now() / 1000)) return null;
    if (!['admin', 'customer'].includes(decoded.role)) return null;
    if (!Number.isInteger(decoded.sessionVersion)) return null;
    return decoded;
  } catch {
    return null;
  }
}

export function sessionCookie(token, maxAge = TOKEN_TTL_SECONDS) {
  const secure = env.nodeEnv === 'production' ? '; Secure' : '';
  return `${env.authCookieName}=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${secure}`;
}
