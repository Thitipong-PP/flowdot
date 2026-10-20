import { HttpError } from '../utils/http-error.js';

export function validate(schema) {
  return (req, _res, next) => {
    const result = schema.safeParse({ body: req.body, params: req.params, query: req.query });
    if (!result.success) {
      return next(new HttpError(400, 'Request validation failed.', result.error.issues.map(({ path, message }) => ({ path, message }))));
    }
    req.validated = result.data;
    return next();
  };
}
