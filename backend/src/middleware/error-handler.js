import { env } from '../config/env.js';
import { HttpError } from '../utils/http-error.js';

export function errorHandler(error, _req, res, next) {
  if (res.headersSent) return next(error);
  _req.logError = { type: error?.name ?? 'Error', code: typeof error?.code === 'string' || typeof error?.code === 'number' ? String(error.code) : undefined };

  if (error?.code === 11000) {
    return res.status(409).json({ error: { message: 'A profile with this email already exists.' } });
  }

  const statusCode = error instanceof HttpError ? error.statusCode : 500;
  const message = statusCode === 500 && env.nodeEnv === 'production' ? 'Internal server error.' : error.message;
  return res.status(statusCode).json({
    error: {
      message,
      ...(error instanceof HttpError && error.details ? { details: error.details } : {}),
    },
  });
}
