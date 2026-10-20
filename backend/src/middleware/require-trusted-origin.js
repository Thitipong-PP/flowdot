import { env } from '../config/env.js';
import { HttpError } from '../utils/http-error.js';

const mutatingMethods = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export function requireTrustedOrigin(req, _res, next) {
  const origin = req.get('origin');
  if (mutatingMethods.has(req.method) && origin && !env.frontendOrigin.split(',').map((value) => value.trim()).includes(origin)) {
    return next(new HttpError(403, 'Request origin is not allowed.'));
  }
  return next();
}
