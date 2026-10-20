import { HttpError } from '../utils/http-error.js';
import { maskPii } from './pii-masker.js';

// All future model calls must go through this boundary so raw PII cannot be sent accidentally.
export async function requestLlmCompletion({ system, messages }) {
  const sanitized = maskPii({ system, messages });
  if (!process.env.LLM_API_URL || !process.env.LLM_API_KEY) {
    throw new HttpError(503, 'AI assistant is not configured yet.');
  }
  const response = await fetch(process.env.LLM_API_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${process.env.LLM_API_KEY}` },
    body: JSON.stringify({ model: process.env.LLM_MODEL, messages: [
      { role: 'system', content: sanitized.system },
      ...sanitized.messages.map(({ role, content }) => ({ role, content })),
    ] }),
    signal: AbortSignal.timeout(20_000),
  });
  if (!response.ok) throw new HttpError(response.status >= 500 ? 503 : 502, 'AI assistant request failed.');
  return response.json();
}
