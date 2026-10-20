import { Router } from 'express';
import mongoose from 'mongoose';
import { env } from '../config/env.js';

const router = Router();

router.get('/', async (_req, res) => {
  const database = mongoose.connection.readyState === 1 ? 'connected' : 'disconnected';
  let assistant = 'not_configured';
  if (env.aiServiceUrl && env.aiServiceToken) {
    try {
      const response = await fetch(`${env.aiServiceUrl}/health`, { signal: AbortSignal.timeout(3000) });
      assistant = response.ok ? 'reachable' : 'unavailable';
    } catch {
      assistant = 'unavailable';
    }
  }
  const status = database === 'connected' ? 200 : 503;
  return res.status(status).json({ data: {
    status: database === 'connected' ? 'ok' : 'unavailable',
    database,
    assistant,
  } });
});

export default router;
