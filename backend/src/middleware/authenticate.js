import { env } from '../config/env.js';
import { UserAccount } from '../models/user-account.js';
import { HttpError } from '../utils/http-error.js';
import { verifySessionToken } from '../services/auth-service.js';

export async function authenticate(req, _res, next) {
  const cookies = Object.fromEntries((req.headers.cookie ?? '').split(';').map((part) => {
    const index = part.indexOf('=');
    return index < 0 ? ['', ''] : [part.slice(0, index).trim(), decodeURIComponent(part.slice(index + 1).trim())];
  }).filter(([key]) => key));
  const claims = verifySessionToken(cookies[env.authCookieName] ?? '');
  if (!claims) return next(new HttpError(401, 'Please sign in to continue.'));

  try {
    const account = await UserAccount.findById(claims.sub).select('role customerId active sessionVersion').lean();
    if (!account?.active || account.role !== claims.role || account.sessionVersion !== claims.sessionVersion || (account.customerId?.toString() ?? null) !== claims.customerId) {
      return next(new HttpError(401, 'Your session is no longer valid.'));
    }
    req.auth = { accountId: account._id.toString(), customerId: account.customerId?.toString() ?? null, role: account.role };
    return next();
  } catch (error) {
    return next(error);
  }
}

export function requireRole(role) {
  return (req, _res, next) => req.auth?.role === role
    ? next()
    : next(new HttpError(403, 'You do not have access to this resource.'));
}
